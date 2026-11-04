# QA de la invitación enviada (receta verificada 28/08)

Tras `send_client_invite.py`, verificar el correo REAL desde la bandeja del remitente
(no confiar solo en el 200 del send). Receta completa, ejecutada con éxito en el piloto Nancy.

## Pasos

1. Obtener access_token de la conexión remitente (`neuralcrew-gmail`): mismo
   descifrado AP → refresh que usa `send_client_invite.py::get_access_token()`
   (`{iv,data}` HEX, AES-256-CBC key cruda de `AP_ENCRYPTION_KEY`, librería `cryptography`).
2. Leer el mensaje enviado:
   `GET https://gmail.googleapis.com/gmail/v1/users/me/messages/{id}?format=full`
   con `Authorization: Bearer <token>`.
3. Extraer headers: `From`, `To`, `Subject` desde `payload.headers`.
4. Caminar `payload.parts` buscando `mimeType == text/html`, decodificar
   `body.data` (base64url) recursivamente.
5. Chequear (los 7 del piloto):
   - cabecera `NEURALCREW` + `LABS` presentes
   - sello `MARKETING POWERED BY AI`
   - 3 botones: `Conectar Gmail`, `Conectar Drive`, `Conectar Calendar`
   - los 3 links `connection=<slug>-gmail|drive|calendar`
   - firma `Jonathan Parra` + `Founder`
   - pie `316 691 0728` + `captain@neuralcrewlabs.com`
   - correo objetivo visible en el HTML

## Resultado esperado (piloto Nancy 28/08)

From: `NeuralCrew Labs <captain@neuralcrewlabs.com>` · Subject:
"Nancy, conecta tu cuenta con NeuralCrew Labs" · HTML 6139 bytes · 7/7 checks OK.

## Lección del incidente previo

El primer intento (enviado desde jonathaun124 con formato distinto y solo Gmail)
quedó INVÁLIDO para Jonathan: los correos institucionales salen SIEMPRE de
captain@ con firma de Founder y formato estándar de 3 botones. Antes del primer
envío a un cliente con el template, confirmar remitente+formato con Jonathan;
después, el estándar ya no se pregunta.
