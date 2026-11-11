const crypto = require('crypto');
const https = require('https');
const cp = require('child_process');

const key = 'd0d965cde2b91da7871afb16a9fe2717';
function decrypt(val) {
  const iv = Buffer.from(val.iv, 'hex');
  const data = Buffer.from(val.data, 'hex');
  const decipher = crypto.createDecipheriv('aes-256-cbc', Buffer.from(key), iv);
  let decrypted = decipher.update(data);
  return JSON.parse(Buffer.concat([decrypted, decipher.final()]).toString());
}

async function getGoldenToken() {
  const raw = cp.execSync("docker exec ap-db psql -U postgres -d activepieces -t -A -c \"SELECT value FROM app_connection WHERE id = 'TEd5XvMY397uFjXL4iGRu'\"").toString();
  const goldenDec = decrypt(JSON.parse(raw));
  const reqBody = JSON.stringify({
    refreshToken: goldenDec.refresh_token,
    pieceName: '@activepieces/piece-google-sheets',
    clientId: goldenDec.client_id,
    edition: 'COMMUNITY',
    authorizationMethod: goldenDec.authorization_method,
    tokenUrl: goldenDec.token_url
  });

  return new Promise((resolve, reject) => {
    const req = https.request('https://secrets.activepieces.com/refresh', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(reqBody)
      }
    }, (res) => {
      let body = '';
      res.on('data', chunk => body += chunk);
      res.on('end', () => {
        const data = JSON.parse(body);
        resolve(data.access_token);
      });
    });
    req.on('error', reject);
    req.write(reqBody);
    req.end();
  });
}

function sheetsRequest(token, path, method, payload) {
  return new Promise((resolve, reject) => {
    const opts = {
      hostname: 'sheets.googleapis.com',
      path: path,
      method: method,
      headers: {
        'Authorization': 'Bearer ' + token
      }
    };
    if (payload) {
      opts.headers['Content-Type'] = 'application/json';
      opts.headers['Content-Length'] = Buffer.byteLength(payload);
    }
    const req = https.request(opts, (res) => {
      let body = '';
      res.on('data', chunk => body += chunk);
      res.on('end', () => {
        try {
          resolve({ status: res.statusCode, data: JSON.parse(body) });
        } catch(e) {
          resolve({ status: res.statusCode, raw: body });
        }
      });
    });
    req.on('error', reject);
    if (payload) req.write(payload);
    req.end();
  });
}

async function run() {
  const token = await getGoldenToken();
  const spreadsheetId = '1j0vsPs4R4owvm_gisidizO0j0xckeZpK4z-Mev2xYu0';

  // 1. Get current sheets
  const metaRes = await sheetsRequest(token, '/v4/spreadsheets/' + spreadsheetId, 'GET');
  const existingSheets = metaRes.data.sheets;
  console.log('Existing sheets:', existingSheets.map(s => s.properties.title));

  let septSheet = existingSheets.find(s => s.properties.title === 'Informe' || s.properties.title === 'Informe Septiembre');
  let octSheet = existingSheets.find(s => s.properties.title === 'Informe Octubre');

  const setupRequests = [];

  // Rename 'Informe' to 'Informe Septiembre' if named 'Informe'
  if (septSheet && septSheet.properties.title === 'Informe') {
    setupRequests.push({
      updateSheetProperties: {
        properties: {
          sheetId: septSheet.properties.sheetId,
          title: 'Informe Septiembre'
        },
        fields: 'title'
      }
    });
  }

  // Create 'Informe Octubre' if it doesn't exist
  let octSheetId = octSheet ? octSheet.properties.sheetId : null;
  if (!octSheet) {
    octSheetId = 948201582; // deterministic ID for October
    setupRequests.push({
      addSheet: {
        properties: {
          sheetId: octSheetId,
          title: 'Informe Octubre',
          index: 2,
          gridProperties: {
            rowCount: 10508,
            columnCount: 26
          }
        }
      }
    });
  }

  if (setupRequests.length > 0) {
    console.log('Executing tab creation / rename...');
    const res = await sheetsRequest(token, '/v4/spreadsheets/' + spreadsheetId + ':batchUpdate', 'POST', JSON.stringify({ requests: setupRequests }));
    console.log('Setup tabs status:', res.status);
    if (res.status !== 200) {
      console.error('Error setup tabs:', res.data);
      return;
    }
  }

  // 2. Setup batch formatting for 'Informe Octubre'
  const octFormatRequests = [
    // Ensure grid properties
    {
      updateSheetProperties: {
        properties: {
          sheetId: octSheetId,
          gridProperties: {
            rowCount: 10508,
            columnCount: 26
          }
        },
        fields: 'gridProperties(rowCount,columnCount)'
      }
    },
    // Col A width: 282
    {
      updateDimensionProperties: {
        range: { sheetId: octSheetId, dimension: 'COLUMNS', startIndex: 0, endIndex: 1 },
        properties: { pixelSize: 282 },
        fields: 'pixelSize'
      }
    },
    // Col B width: 214
    {
      updateDimensionProperties: {
        range: { sheetId: octSheetId, dimension: 'COLUMNS', startIndex: 1, endIndex: 2 },
        properties: { pixelSize: 214 },
        fields: 'pixelSize'
      }
    },
    // Col C width: 100
    {
      updateDimensionProperties: {
        range: { sheetId: octSheetId, dimension: 'COLUMNS', startIndex: 2, endIndex: 6 },
        properties: { pixelSize: 100 },
        fields: 'pixelSize'
      }
    },
    // Col G to M (startIndex 6, endIndex 13) hiddenByUser: true
    {
      updateDimensionProperties: {
        range: { sheetId: octSheetId, dimension: 'COLUMNS', startIndex: 6, endIndex: 13 },
        properties: { hiddenByUser: true, pixelSize: 100 },
        fields: 'hiddenByUser,pixelSize'
      }
    },
    // Merge C8:E8 (row 7, col 2 to 5)
    {
      mergeCells: {
        range: { sheetId: octSheetId, startRowIndex: 7, endRowIndex: 8, startColumnIndex: 2, endColumnIndex: 5 },
        mergeType: 'MERGE_ALL'
      }
    },
    // Format B3 as DATE 'mmmm yyyy'
    {
      repeatCell: {
        range: { sheetId: octSheetId, startRowIndex: 2, endRowIndex: 3, startColumnIndex: 1, endColumnIndex: 2 },
        cell: { userEnteredFormat: { numberFormat: { type: 'DATE', pattern: 'mmmm yyyy' } } },
        fields: 'userEnteredFormat.numberFormat'
      }
    },
    // Format B5, B7, B8 as CURRENCY '[$ $]#,##0'
    {
      repeatCell: {
        range: { sheetId: octSheetId, startRowIndex: 4, endRowIndex: 5, startColumnIndex: 1, endColumnIndex: 2 },
        cell: { userEnteredFormat: { numberFormat: { type: 'CURRENCY', pattern: '[$ $]#,##0' } } },
        fields: 'userEnteredFormat.numberFormat'
      }
    },
    {
      repeatCell: {
        range: { sheetId: octSheetId, startRowIndex: 5, endRowIndex: 6, startColumnIndex: 1, endColumnIndex: 2 },
        cell: { userEnteredFormat: { numberFormat: { type: 'NUMBER', pattern: '#,##0' } } },
        fields: 'userEnteredFormat.numberFormat'
      }
    },
    {
      repeatCell: {
        range: { sheetId: octSheetId, startRowIndex: 6, endRowIndex: 8, startColumnIndex: 1, endColumnIndex: 2 },
        cell: { userEnteredFormat: { numberFormat: { type: 'CURRENCY', pattern: '[$ $]#,##0' } } },
        fields: 'userEnteredFormat.numberFormat'
      }
    },
    // Format C11:C41 as CURRENCY (31 days in October)
    {
      repeatCell: {
        range: { sheetId: octSheetId, startRowIndex: 10, endRowIndex: 41, startColumnIndex: 2, endColumnIndex: 3 },
        cell: { userEnteredFormat: { numberFormat: { type: 'CURRENCY', pattern: '[$ $]#,##0' } } },
        fields: 'userEnteredFormat.numberFormat'
      }
    },
    // Format C45 as CURRENCY
    {
      repeatCell: {
        range: { sheetId: octSheetId, startRowIndex: 44, endRowIndex: 45, startColumnIndex: 2, endColumnIndex: 3 },
        cell: { userEnteredFormat: { numberFormat: { type: 'CURRENCY', pattern: '[$ $]#,##0' } } },
        fields: 'userEnteredFormat.numberFormat'
      }
    },
    // Format C52:C67 as CURRENCY
    {
      repeatCell: {
        range: { sheetId: octSheetId, startRowIndex: 51, endRowIndex: 67, startColumnIndex: 2, endColumnIndex: 3 },
        cell: { userEnteredFormat: { numberFormat: { type: 'CURRENCY', pattern: '[$ $]#,##0' } } },
        fields: 'userEnteredFormat.numberFormat'
      }
    }
  ];

  console.log('Sending octFormat batchUpdate...');
  const fmtRes = await sheetsRequest(
    token,
    '/v4/spreadsheets/' + spreadsheetId + ':batchUpdate',
    'POST',
    JSON.stringify({ requests: octFormatRequests })
  );
  console.log('octFormat batchUpdate status:', fmtRes.status);

  // 3. Build October matrix (67 rows, 13 cols)
  const matrix = [];
  for (let i = 0; i < 67; i++) matrix.push(new Array(13).fill(''));

  // Row 1 (index 0)
  matrix[0][0] = 'Bre-B Golden — Informe octubre 2026';

  // Row 2 (index 1)
  matrix[1][0] = 'Actualizado';
  matrix[1][1] = '=TEXT(NOW();"DD/MM/YYYY HH:MM")&" (Colombia)"';
  matrix[1][6] = "=ARRAYFORMULA(IF('Bre-B Golden — Pagos'!A2:A10008=\"\";\"\";'Bre-B Golden — Pagos'!A2:A10008))";
  matrix[1][7] = "=ARRAYFORMULA(IF('Bre-B Golden — Pagos'!B2:B10008=\"\";\"\";'Bre-B Golden — Pagos'!B2:B10008))";
  matrix[1][8] = "=ARRAYFORMULA(IF('Bre-B Golden — Pagos'!C2:C10008=\"\";\"\";'Bre-B Golden — Pagos'!C2:C10008))";
  matrix[1][9] = "=ARRAYFORMULA(IF('Bre-B Golden — Pagos'!D2:D10008=\"\";\"\";'Bre-B Golden — Pagos'!D2:D10008))";
  matrix[1][10] = "=ARRAYFORMULA(IF('Bre-B Golden — Pagos'!E2:E10008=\"\";\"\";'Bre-B Golden — Pagos'!E2:E10008))";
  matrix[1][11] = '=ARRAYFORMULA(IF(G2:G10508=\"\";0;IFERROR(VALUE(TRIM(SUBSTITUTE(H2:H10508;\"$\";\"\")));0)))';
  matrix[1][12] = '=ARRAYFORMULA(IF(G2:G10508=\"\";\"\";SUBSTITUTE(IF(ISNUMBER(G2:G10508);TEXT(G2:G10508;\"YYYY-MM-DD HH:MM\");G2:G10508);\"/\";\"-\")))';

  // Row 3 (index 2)
  matrix[2][0] = 'Período';
  matrix[2][1] = 46296; // October 2026

  // Row 5 (index 4)
  matrix[4][0] = 'TOTAL RECAUDADO';
  matrix[4][1] = '=SUMIF(M2:M10508;"2026-10*";L2:L10508)';

  // Row 6 (index 5)
  matrix[5][0] = 'PAGOS';
  matrix[5][1] = '=COUNTIF(M2:M10508;"2026-10*")';

  // Row 7 (index 6)
  matrix[6][0] = 'TICKET PROMEDIO';
  matrix[6][1] = '=IF(B6=0;0;B5/B6)';

  // Row 8 (index 7)
  matrix[7][0] = 'PAGO MÁS ALTO';
  matrix[7][1] = '=ARRAYFORMULA(MAX(IF(LEFT(M2:M10508;7)="2026-10";L2:L10508)))';
  matrix[7][2] = '=INDEX(I2:I10508;MATCH(B8&"|2026-10";ARRAYFORMULA(L2:L10508&"|"&LEFT(M2:M10508;7));0))';

  // Row 10 (index 9)
  matrix[9][0] = 'POR DÍA';
  matrix[9][1] = 'Pagos';
  matrix[9][2] = 'Total';

  // Rows 11-41 (indices 10-40) - 31 days in October
  for (let d = 1; d <= 31; d++) {
    const rowIdx = 9 + d; // 10 to 40
    const dayStr = '2026-10-' + (d < 10 ? '0' + d : '' + d);
    const rowNum = rowIdx + 1;
    matrix[rowIdx][0] = "'" + dayStr;
    matrix[rowIdx][1] = '=COUNTIF($M$2:$M$10508;$A' + rowNum + '&"*")';
    matrix[rowIdx][2] = '=SUMIF($M$2:$M$10508;$A' + rowNum + '&"*";$L$2:$L$10508)';
  }

  // Row 44 (index 43)
  matrix[43][0] = 'POR CUENTA DESTINO';
  matrix[43][1] = 'Pagos';
  matrix[43][2] = 'Total';

  // Row 45 (index 44)
  matrix[44][0] = '*****7028';
  matrix[44][1] = '=COUNTIFS($J$2:$J$10508;$A45;$M$2:$M$10508;"2026-10*")';
  matrix[44][2] = '=SUMIFS($L$2:$L$10508;$J$2:$J$10508;$A45;$M$2:$M$10508;"2026-10*")';

  // Row 51 (index 50)
  matrix[50][0] = 'TOP REMITENTES OCTUBRE';
  matrix[50][1] = 'Pagos';
  matrix[50][2] = 'Total';

  // Top remitentes for October (including current October payers + key repeat payers)
  const topRemitentesOct = [
    'HELMER ALEXIS PARRA GUZMAN',
    'ANGI TATIANA RUIZ OSORIO',
    'ALBERTO BUENO IBARRA BUENO',
    'AMANDA MORALES AYA',
    'LESTER ENRIQUE SIACHOQUE ROMERO',
    'FERNANDO CASTRO CHAPARRO',
    'JOSE ISRAEL AMORTEGUI SANCHEZ',
    'ERENY YESED ROJAS DIAZ',
    'OMAR STEVEN ORTIZ SANCHEZ',
    'LUNIOR CHEVEL',
    'BLANCA ROJAS ZAMBRANO',
    'OLGA LUCIA LOPEZ RIOS',
    'BENILDA DIAZ CASTRO',
    'SAIDA MARIA AGAMEZ MARTINEZ',
    'HEIDY GERALDINE CACERES NONTOA'
  ];

  for (let t = 0; t < topRemitentesOct.length; t++) {
    const rowIdx = 51 + t; // 51 to 65
    const rowNum = rowIdx + 1;
    matrix[rowIdx][0] = topRemitentesOct[t];
    matrix[rowIdx][1] = '=COUNTIFS($I$2:$I$10508;$A' + rowNum + ';$M$2:$M$10508;"2026-10*")';
    matrix[rowIdx][2] = '=SUMIFS($L$2:$L$10508;$I$2:$I$10508;$A' + rowNum + ';$M$2:$M$10508;"2026-10*")';
  }

  console.log("Writing values to 'Informe Octubre'!A1:M67...");
  const valRes = await sheetsRequest(
    token,
    '/v4/spreadsheets/' + spreadsheetId + '/values/' + encodeURIComponent("'Informe Octubre'!A1:M67") + '?valueInputOption=USER_ENTERED',
    'PUT',
    JSON.stringify({
      range: "'Informe Octubre'!A1:M67",
      majorDimension: 'ROWS',
      values: matrix
    })
  );
  console.log('october values.update result:', valRes.status, valRes.data?.updatedCells, 'cells updated');
}

run().catch(console.error);
