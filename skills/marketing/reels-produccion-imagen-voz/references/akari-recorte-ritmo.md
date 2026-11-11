# Recorte de ritmo con Akari sin nuevas generaciones

- Verifica el editor en el HOST correspondiente antes de declararlo ausente. Una búsqueda desde el runtime del agente no prueba que no exista en otro directorio o contexto de permisos. Usa `terminal` para comprobar el CLI y leer sus instrucciones reales.
- Reutiliza el master visual sin audio del montaje aprobado cuando solo cambie el ritmo. Recorta imagen y reposiciona los WAV originales con la misma transformación temporal; no aceleres voz ni alteres diseño para arreglar esperas.
- Cuantiza keep-ranges a fotogramas. Asegura que el habla completa quede fuera de ambos handles del fundido. Un dissolve de 0.1 s a 30 fps ocupa tres fotogramas; distingue ese tiempo de la pausa audible real.
- Conserva una cama musical continua y usa ducking con la narración. Recortar el soundtrack mezclado anterior también corta la continuidad musical.
- Empaqueta TODOS los inputs dentro del proyecto Akari con copias byte-idénticas verificadas por SHA-256. El recibo rechaza rutas que escapan del project root, incluidos symlinks externos. Escribe la salida del editor dentro del proyecto y conserva anteriores versiones.
- Ejecuta realmente edit-lint con media, render-cut --plan-only y luego render-cut, sin --force. Un plan o handoff no es un render. Verifica el recibo y el MP4 de salida.
- El master Akari puede ser all-intra y pesado. Conserva ese master y genera una copia de distribución GOP normal/faststart, identificándola como derivado. Revalida duración, frames, resolución, decode y audio de ESA copia.
- Conserva warnings INCONCLUSIVE del QC; no cambies el informe original a PASS. Mide separadamente el audio decodificado final y reporta los límites de la aceptación perceptual.
- Contrasta las cuatro formas de onda completas contra el soundtrack final para comprobar identidad, velocidad y posición. Esto no certifica sincronía fonémica de la boca.
- Entrega el MP4 real con MEDIA y solicita revisión independiente del archivo existente. Mantén pendientes aprobación humana y publicación hasta su autorización.
