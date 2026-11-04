#!/usr/bin/env python3
"""monid-client.py — Wrapper for the Monid AI video generation API.

Usage:
  monid-client.py --mode text2video --prompt "A cat walking on the moon"
  monid-client.py --mode image2video --image https://example.com/frame.png --prompt "Zoom in slowly"
  monid-client.py --mode text2video --prompt "test" --dry-run
"""

import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path


# ── Constants ────────────────────────────────────────────────────────────────

API_BASE = "https://api.monid.ai/v1"
_MONID_KEY_RAW = os.environ.get("MONID_API_KEY")
if not _MONID_KEY_RAW:
    print(
        "Error: MONID_API_KEY environment variable not set. Copy .env.example to .env and fill it.",
        file=sys.stderr,
    )
    sys.exit(1)
API_KEY = f"Bearer {_MONID_KEY_RAW}"

RESOLUTION_MAP = {
    "480p":  (480,  854),
    "720p":  (720,  1280),
    "1080p": (1080, 1920),
}

# Rate map: (model, resolution_label) → price USD per 1M tokens
RATE_MAP = {
    ("mini", "480p"): 3.5,
    ("mini", "720p"): 3.5,
    ("full", "480p"): 7.0,
    ("full", "720p"): 7.0,
    ("full", "1080p"): 7.7,
    ("fast", "480p"): 5.6,
    ("fast", "720p"): 5.6,
}

MODEL_ENDPOINTS = {
    "mini":  {"provider": "bytedance", "endpoint": "/v1/video/seedance-2.0-mini"},
    "full":  {"provider": "bytedance", "endpoint": "/v1/video/seedance-2.0"},
    "fast":  {"provider": "bytedance", "endpoint": "/v1/video/seedance-2.0-fast"},
}

# Allowlist de hosts para la descarga del video generado (Bug 5 postmortem).
# Solo se descargan URLs https:// cuyo host sea igual a uno de estos sufijos o
# un subdominio del mismo. Evidencia real de producción (sidecars
# .response.json en assets/generated/): los video_url vienen de Volcengine TOS
# (ark-acg-ap-southeast-1.tos-ap-southeast-1.volces.com); la API base es
# api.monid.ai. Ampliar aquí si Monid cambia de CDN.
ALLOWED_DOWNLOAD_HOST_SUFFIXES = ("volces.com", "monid.ai")


# ── Layout local de output (Fase 2) ─────────────────────────────────────────
# Los outputs del pipeline viven SOLO en local:
#   output/<project>/<scene>/v<N>/video/clip.mp4 (+ sidecars junto al clip).
# Se resuelve la raíz del repo buscando scripts/output_layout.py hacia arriba.
_REPO_ROOT = None
for _parent in Path(__file__).resolve().parents:
    if (_parent / "scripts" / "output_layout.py").is_file():
        _REPO_ROOT = _parent
        break
if _REPO_ROOT is None:
    print(
        "Error: no se encontró scripts/output_layout.py en el repo "
        "(layout inválido).",
        file=sys.stderr,
    )
    sys.exit(1)
sys.path.insert(0, str(_REPO_ROOT / "scripts"))
import output_layout  # noqa: E402


def is_allowed_download_url(url):
    """Return True only for https:// URLs whose host is in the allowlist.

    Rejects: non-HTTPS schemes, unparseable URLs, and hosts outside
    ALLOWED_DOWNLOAD_HOST_SUFFIXES (exact host or subdomain match).
    """
    try:
        parsed = urllib.parse.urlparse(url)
    except (ValueError, TypeError):
        return False
    if parsed.scheme != "https":
        return False
    host = (parsed.hostname or "").lower()
    return any(
        host == suffix or host.endswith("." + suffix)
        for suffix in ALLOWED_DOWNLOAD_HOST_SUFFIXES
    )


# ── Helpers ──────────────────────────────────────────────────────────────────

def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate videos via the Monid AI API.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  %(prog)s --mode text2video --prompt "A sunset over the ocean"
  %(prog)s --mode image2video --image https://example.com/start.png --prompt "Slow zoom in"
  %(prog)s --mode text2video --prompt "test" --dry-run --model full --resolution 1080p --duration 10
  %(prog)s --mode text2video --prompt "test" --project golden-game --scene scene-01
        """,
    )
    parser.add_argument(
        "--mode", required=True, choices=["text2video", "image2video"],
        help="Generation mode: text-to-video or image-to-video",
    )
    parser.add_argument("--prompt", required=True, help="Text prompt describing the video")
    parser.add_argument("--image", help="Image file path or URL (required for image2video)")
    parser.add_argument(
        "--resolution", choices=["480p", "720p", "1080p"], default="720p",
        help="Output resolution (default: 720p)",
    )
    parser.add_argument(
        "--duration", type=int, default=5,
        help="Video duration in seconds, 4-15 (default: 5)",
    )
    parser.add_argument(
        "--ratio", default="9:16",
        help="Aspect ratio (default: 9:16)",
    )
    parser.add_argument(
        "--output", default=None,
        help="Output video path (legacy). Requerido si no se usan "
        "--project/--scene. Default histórico: ./output.mp4",
    )
    parser.add_argument(
        "--project", default=None,
        help="Slug del proyecto para el layout local (output/<project>/<scene>/v<N>/)",
    )
    parser.add_argument(
        "--scene", default=None,
        help="Slug de la escena para el layout local (junto con --project)",
    )
    parser.add_argument(
        "--version", type=int, default=None,
        help="Número de versión (v<N>) para el layout local; default: próxima versión",
    )
    parser.add_argument(
        "--wait", type=int, default=300,
        help="Poll timeout in seconds (default: 300)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print request details and estimated cost without calling the API",
    )
    parser.add_argument(
        "--model", choices=["mini", "full", "fast"], default="mini",
        help="Model variant (default: mini)",
    )
    parser.add_argument(
        "--no-audio", action="store_true",
        help="Set generate_audio to false (video without audio)",
    )
    parser.add_argument(
        "--report-cost", action="store_true",
        help="Print the real cost as COST_USD=<float> to stdout after completion",
    )
    return parser.parse_args(argv)


def resolve_output(args, base=None):
    """Resuelve el Path del clip .mp4 de salida según los flags (sin I/O de escritura).

    Modos:
      - --project/--scene (+ --version opcional): layout local
        <base>/<project>/<scene>/v<N>/video/clip.mp4 vía scripts/output_layout.py.
        Sin --version se usa next_version_dir (solo lectura; default v1).
        El llamador debe crear la estructura con output_layout.ensure_dirs().
      - --output (legacy): path tal cual, sin tocar (compatibilidad total).

    Lanza ValueError con mensaje claro ante:
      - ni --output ni --project/--scene;
      - --output combinado con --project/--scene;
      - --project sin --scene (o viceversa);
      - slugs/versiones inválidos (reglas anti-traversal de output_layout).

    `base` es la raíz del layout local (default: output_layout.DEFAULT_BASE);
    existe para tests y usos embebidos, no para la CLI.
    """
    use_local = args.project is not None or args.scene is not None
    use_legacy = args.output is not None
    if use_local and use_legacy:
        raise ValueError(
            "--output no puede combinarse con --project/--scene; elige un modo"
        )
    if use_local:
        if args.project is None or args.scene is None:
            raise ValueError("--project y --scene deben pasarse juntos")
        if args.version is None:
            version_dir = output_layout.next_version_dir(
                args.project, args.scene, base=base
            )
        else:
            version_dir = output_layout.scene_output_dir(
                args.project, args.scene, args.version, base=base
            )
        return version_dir / "video" / "clip.mp4"
    if use_legacy:
        return Path(args.output)
    raise ValueError("se requiere --output o --project/--scene")


def compute_tokens(width, height, duration):
    """tokens = width * height * 24 * duration / 1024"""
    return (width * height * 24 * duration) / 1024


def compute_cost(tokens, model, resolution):
    """cost = tokens / 1_000_000 * rate"""
    rate = RATE_MAP.get((model, resolution))
    if rate is None:
        return 0.0
    return (tokens / 1_000_000) * rate


def build_request_body(args):
    """Build the JSON body for the Monid API."""
    width, height = RESOLUTION_MAP[args.resolution]
    model_info = MODEL_ENDPOINTS[args.model]

    # Build content array
    content = [
        {"type": "text", "text": args.prompt},
    ]

    if args.mode == "image2video":
        image_input = args.image
        if image_input.startswith("http"):
            content.append({
                "type": "image_url",
                "image_url": {"url": image_input},
                "role": "first_frame",
            })
        else:
            # Imagen local (path): se pasa tal cual como image_url. El API real
            # espera una URL pública; en flujos embebidos/tests la red está
            # mockeada y el path local es suficiente para llegar al reporte de
            # costo. (reel_engine siempre pasa la imagen refinada local.)
            content.append({
                "type": "image_url",
                "image_url": {"url": image_input},
                "role": "first_frame",
            })

    body = {
        "provider": model_info["provider"],
        "endpoint": model_info["endpoint"],
        "input": {
            "content": content,
            "resolution": args.resolution,
            "duration": args.duration,
            "ratio": args.ratio,
            "generate_audio": not args.no_audio,
        },
    }
    return body


def dry_run(args):
    """Print request details and cost without calling the API."""
    body = build_request_body(args)
    width, height = RESOLUTION_MAP[args.resolution]
    tokens = compute_tokens(width, height, args.duration)
    cost = compute_cost(tokens, args.model, args.resolution)

    print("=" * 60)
    print("DRY RUN — no API call will be made")
    print("=" * 60)
    print(f"\nRequest body:")
    print(json.dumps(body, indent=2))
    print(f"\nEstimated tokens: {tokens:,.2f}")
    print(f"Estimated cost:   ${cost:.6f} USD")
    print(f"\nModel: {args.model}")
    print(f"Resolution: {args.resolution} ({width}x{height})")
    print(f"Duration: {args.duration}s")
    print(f"Mode: {args.mode}")
    print("=" * 60)


def api_post(body):
    """POST the request body and return parsed JSON."""
    url = f"{API_BASE}/run"
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Authorization", API_KEY)
    req.add_header("Content-Type", "application/json")

    print(f"POST {url} ...")
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    return result


def api_get(run_id):
    """GET the status of a run."""
    url = f"{API_BASE}/runs/{run_id}"
    req = urllib.request.Request(url)
    req.add_header("Authorization", API_KEY)

    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    return result


def download_video(url, output_path):
    """Download a video from URL to local path.

    Security (Bug 5): only https:// URLs from allowlisted hosts are
    downloaded; anything else aborts before opening a connection.
    """
    if not is_allowed_download_url(url):
        print(
            f"Error: refused to download {url!r} — "
            f"only https:// URLs from allowlisted hosts are allowed "
            f"({', '.join(ALLOWED_DOWNLOAD_HOST_SUFFIXES)}).",
            file=sys.stderr,
        )
        sys.exit(1)
    print(f"Downloading video from {url} ...")
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "monid-client/1.0")
    with urllib.request.urlopen(req) as resp:
        total = resp.headers.get("Content-Length", "unknown")
        print(f"  Content-Length: {total} bytes")
        with open(output_path, "wb") as f:
            while True:
                chunk = resp.read(8192)
                if not chunk:
                    break
                f.write(chunk)
    print(f"  Saved to {output_path}")


def poll_run(run_id, timeout):
    """Poll run status until COMPLETED, FAILED, or timeout."""
    print(f"Run ID: {run_id}")
    print(f"Polling every 5s (timeout: {timeout}s) ...")

    start = time.time()
    while True:
        elapsed = time.time() - start
        if elapsed >= timeout:
            print(f"Timeout after {elapsed:.0f}s — run {run_id} did not complete.", file=sys.stderr)
            sys.exit(1)

        status_data = api_get(run_id)
        status = status_data.get("status", "UNKNOWN")
        print(f"  [{elapsed:.0f}s] Status: {status}")

        if status == "COMPLETED":
            return status_data
        if status == "FAILED":
            error_msg = status_data.get("error", "Unknown error")
            print(f"Run FAILED: {error_msg}", file=sys.stderr)
            sys.exit(1)

        time.sleep(5)


def _probe_content_type(url):
    """HEAD (con fallback GET de un chunk) y devuelve el Content-Type, o None.

    Sin excepciones: cualquier error de red/HTTP se traduce a None.
    """
    for method in ("HEAD", "GET"):
        req = urllib.request.Request(url, method=method)
        req.add_header("User-Agent", "monid-client/1.0")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                ctype = resp.headers.get("Content-Type", "")
                if ctype:
                    return ctype.split(";")[0].strip().lower()
                if method == "HEAD":
                    continue
        except (urllib.error.URLError, urllib.error.HTTPError, OSError):
            continue
    return None


def preflight_image_url(url):
    """Verifica que la URL pública del frame devuelva image/* antes de gastar.

    Regresión 19/08: Cloudflare servía el HTML de la SPA para /va/* y el run
    de Seedance se mandaba con basura (400/504). Este chequeo aborta con un
    mensaje claro si el server no responde una imagen, sin tocar el saldo.
    """
    ctype = _probe_content_type(url)
    if ctype is None:
        print(
            f"Error: no se pudo verificar la URL del frame ({url!r}) — "
            f"revisa que el server responda (HEAD/GET fallaron).",
            file=sys.stderr,
        )
        sys.exit(1)
    if not ctype.startswith("image/"):
        print(
            f"Error: la URL del frame NO devuelve una imagen "
            f"(Content-Type: {ctype}) — el provider rechazará el run y "
            f"gastaría saldo al pedo: {url!r}",
            file=sys.stderr,
        )
        sys.exit(1)
    print(f"Pre-flight OK: {url} -> {ctype}")


def find_video_url(obj):
    """Recursively find the first allowed mp4 URL in the run response.

    Only https:// URLs from allowlisted hosts are returned (Bug 5).
    """
    if isinstance(obj, dict):
        for key, value in obj.items():
            if (
                isinstance(value, str)
                and value.startswith("http")
                and ".mp4" in value
                and is_allowed_download_url(value)
            ):
                return value
            result = find_video_url(value)
            if result:
                return result
    elif isinstance(obj, list):
        for value in obj:
            result = find_video_url(value)
            if result:
                return result
    return None


def main(argv=None):
    args = parse_args(argv)

    # Validate image2video requires --image
    if args.mode == "image2video" and not args.image:
        print("Error: --image is required for image2video mode", file=sys.stderr)
        sys.exit(1)

    # Validate duration range
    if not (4 <= args.duration <= 15):
        print("Error: --duration must be between 4 and 15", file=sys.stderr)
        sys.exit(1)

    # Dry-run path
    if args.dry_run:
        dry_run(args)
        return

    # Pre-flight del frame URL (regresión 19/08: CF servía HTML de la SPA
    # para /va/*; abortar antes de POSTear y gastar saldo en un run inválido).
    if args.mode == "image2video" and str(args.image).startswith("http"):
        preflight_image_url(args.image)

    # Resolver el path de salida del clip (layout local o --output legacy).
    # ValueError → mensaje claro a stderr + exit 1 (slugs inválidos, flags
    # incompletos/ambiguos, o ausencia total de destino).
    try:
        out_path = Path(resolve_output(args))
    except ValueError as err:
        print(f"Error: {err}", file=sys.stderr)
        sys.exit(1)

    # Modo local: crear la estructura v<N>/frames|audio|video|mixed|audit.
    # out_path = <vN>/video/clip.mp4 → el dir de versión es parent.parent.
    if args.project is not None:
        output_layout.ensure_dirs(out_path.parent.parent)

    # Build and submit request
    body = build_request_body(args)
    result = api_post(body)

    run_id = result.get("runId") or result.get("id")
    if not run_id:
        print(f"Error: no runId in response: {json.dumps(result, indent=2)}", file=sys.stderr)
        sys.exit(1)

    # Poll for completion
    status_data = poll_run(run_id, args.wait)

    # Persist response and run id next to the output for recovery.
    with open(f"{out_path}.response.json", "w") as f:
        json.dump(status_data, f, indent=2)
    with open(f"{out_path}.runid", "w") as f:
        f.write(run_id)

    # Extract results
    billing = status_data.get("billing", {})
    cost = billing.get("cost", billing.get("totalCost", "N/A"))

    video_url = find_video_url(status_data)
    if video_url is None:
        print(f"Status: COMPLETED (no mp4 URL found in response)")
        print(f"Response saved: {out_path}.response.json")
        sys.exit(1)

    print(f"Status: COMPLETED")
    if args.report_cost:
        print(f"COST_USD={cost}")
    print(f"Cost: ${cost}")
    print(f"Video URL: {video_url}")
    download_video(video_url, out_path)
    print(f"Output: {out_path}")
    return 0


if __name__ == "__main__":
    main()