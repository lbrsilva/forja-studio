"""Gera vários vídeos do Canais a partir de um manifesto JSON.

Exemplo de manifesto:

{
  "base": "http://127.0.0.1:8194",
  "jobs": [
    {"canal_id": "abc123", "briefing": "Como funciona a fotossíntese",
     "formatos": ["tiktok"], "estilo": "auto"},
    {"canal_id": "abc123", "plano": {...}, "briefing": "Revisão do roteiro"}
  ]
}

Uso:
    python estudio/lote.py lote.json --dry-run
    python estudio/lote.py lote.json --wait
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def _req(base, caminho, dados=None, timeout=60):
    url = base.rstrip("/") + caminho
    corpo = json.dumps(dados).encode("utf-8") if dados is not None else None
    pedido = urllib.request.Request(
        url, data=corpo, method="POST" if corpo is not None else "GET",
        headers={"Content-Type": "application/json"} if corpo is not None else {})
    try:
        with urllib.request.urlopen(pedido, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        texto = exc.read().decode("utf-8", errors="replace")[:400]
        raise RuntimeError("HTTP %s em %s: %s" % (exc.code, caminho, texto))
    except urllib.error.URLError as exc:
        raise RuntimeError("não consegui falar com o estúdio em %s: %s" % (base, exc))


def _validar(job, indice):
    if not isinstance(job, dict):
        raise ValueError("job %d não é um objeto" % indice)
    cid = str(job.get("canal_id") or "").strip()
    if not cid:
        raise ValueError("job %d sem canal_id" % indice)
    if not (job.get("briefing") or job.get("plano")):
        raise ValueError("job %d sem briefing nem plano" % indice)
    if job.get("formatos") is not None and not isinstance(job.get("formatos"), list):
        raise ValueError("job %d: formatos precisa ser lista" % indice)
    return cid


def _esperar(base, cid, pid, timeout):
    fim = time.time() + timeout
    while time.time() < fim:
        d = _req(base, "/api/canais/%s/producoes/%s" % (cid, pid))
        estado = d.get("estado") or ""
        if estado in ("aguardando_aprovacao", "concluido", "erro", "cancelado"):
            return estado, d
        time.sleep(5)
    return "tempo_esgotado", {}


def main(argv=None):
    p = argparse.ArgumentParser(description="Gera vários vídeos do Canais a partir de um JSON.")
    p.add_argument("manifesto", help="arquivo JSON com a lista de jobs")
    p.add_argument("--base", default="", help="endereço do estúdio (padrão: o do manifesto ou 127.0.0.1:8194)")
    p.add_argument("--dry-run", action="store_true", help="só valida e mostra os jobs, sem chamar a API")
    p.add_argument("--wait", action="store_true", help="espera cada produção terminar")
    p.add_argument("--timeout", type=int, default=3600, help="segundos de espera por job (padrão: 3600)")
    p.add_argument("--only", default="", help="índices 1-based separados por vírgula")
    args = p.parse_args(argv)

    try:
        manifesto = json.loads(Path(args.manifesto).read_text(encoding="utf-8"))
    except Exception as exc:
        print("não consegui ler o manifesto: %s" % exc, file=sys.stderr)
        return 2
    jobs = manifesto.get("jobs") if isinstance(manifesto, dict) else None
    if not isinstance(jobs, list) or not jobs:
        print("o manifesto precisa ter uma lista 'jobs' não vazia", file=sys.stderr)
        return 2
    base = (args.base or manifesto.get("base") or "http://127.0.0.1:8194").rstrip("/")
    escolhidos = None
    if args.only.strip():
        try:
            escolhidos = {int(x) for x in args.only.split(",") if x.strip()}
        except ValueError:
            print("--only precisa ser uma lista de números, ex.: 1,3,4", file=sys.stderr)
            return 2

    validos = []
    for i, job in enumerate(jobs, 1):
        if escolhidos and i not in escolhidos:
            continue
        try:
            cid = _validar(job, i)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        validos.append((i, cid, job))
    if not validos:
        print("nenhum job selecionado", file=sys.stderr)
        return 2

    if args.dry_run:
        print("base: %s" % base)
        for i, cid, job in validos:
            tipo = "plano pronto" if job.get("plano") else "briefing"
            print("[%d] canal %s · %s · formatos %s" % (
                i, cid, tipo, ",".join(job.get("formatos") or []) or "do canal"))
        print("dry-run: %d job(s), nada foi chamado" % len(validos))
        return 0

    falhas = 0
    for i, cid, job in validos:
        try:
            plano = job.get("plano")
            if not plano:
                d = _req(base, "/api/canais/%s/plano" % cid, {
                    "briefing": job.get("briefing") or "",
                    "formatos": job.get("formatos"),
                    "estilo": job.get("estilo"),
                    "quantas": job.get("quantas"),
                    "duracao": job.get("duracao"),
                }, timeout=max(120, args.timeout))
                plano = d.get("plano")
                if not plano:
                    raise RuntimeError("o estúdio não devolveu plano")
            d = _req(base, "/api/canais/%s/produzir" % cid, {
                "plano": plano,
                "briefing": job.get("briefing") or "",
                "formatos": job.get("formatos"),
                "estilo": job.get("estilo"),
                "legendas": job.get("legendas"),
            }, timeout=max(120, args.timeout))
            prod = d.get("producao") or {}
            pid = prod.get("id")
            if not pid:
                raise RuntimeError("o estúdio não devolveu o id da produção")
            print("[%d/%d] canal %s · produção %s" % (i, len(validos), cid, pid))
            if args.wait:
                estado, _ = _esperar(base, cid, pid, args.timeout)
                print("    %s · %s" % (pid, estado))
                if estado in ("erro", "cancelado", "tempo_esgotado"):
                    falhas += 1
        except Exception as exc:
            falhas += 1
            print("[%d/%d] falhou: %s" % (i, len(validos), exc), file=sys.stderr)
    return 1 if falhas else 0


if __name__ == "__main__":
    raise SystemExit(main())
