#!/usr/bin/env python3
"""Analisa o ritmo de uma referência do HackEdit: detecta os cortes e mede os planos.

Mostra o andamento na barra de Atividade (etapas e porcentagem), e guarda o resultado na referência.
Uso:
  .venv/bin/python analise_referencia.py --id ABC --arquivo projetos/_hackedit/arquivos/x.mov --status projetos/_sync/x.json
"""
import argparse
import json
import re
import statistics
import subprocess
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
from sincronizar import Status  # noqa: E402
HACKEDIT = BASE / "projetos" / "_hackedit.json"
FFMPEG = str(BASE / ".venv" / "bin" / "ffmpeg")


def salvar_resultado(ref_id, analise):
    try:
        lista = json.loads(HACKEDIT.read_text())
    except (OSError, ValueError):
        lista = []
    for x in lista:
        if x.get("id") == ref_id:
            x["analise"] = analise
    HACKEDIT.write_text(json.dumps(lista, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True)
    ap.add_argument("--arquivo", required=True)
    ap.add_argument("--status")
    args = ap.parse_args()
    st = Status(args.status)
    st.d.update(nome=f"Analisar referência · {Path(args.arquivo).name}", tipo="sync")
    try:
        arq = Path(args.arquivo)
        st("Lendo", "Lendo o vídeo de referência…", 2)
        probe = subprocess.run([FFMPEG, "-hide_banner", "-i", str(arq)], capture_output=True, text=True, errors="replace")
        m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", probe.stderr)
        if not m:
            raise RuntimeError("não consegui ler a duração do vídeo")
        dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
        st("Cortes", f"Procurando os cortes em {dur:.0f} s de vídeo…", 5)
        p = subprocess.Popen([FFMPEG, "-hide_banner", "-i", str(arq), "-vf", "select='gt(scene,0.3)',showinfo",
                              "-an", "-f", "null", "-"], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                             text=True, errors="replace")
        cortes, ultimo = [], 0.0
        for linha in p.stderr:
            mm = re.search(r"pts_time:([\d.]+)", linha)
            if mm:
                t = float(mm.group(1))
                if 0 < t < dur:
                    cortes.append(t)
                ultimo = max(ultimo, t)
                if len(cortes) % 10 == 0:
                    st("Cortes", f"{len(cortes)} corte(s) encontrado(s)…", 5 + int(80 * min(ultimo / dur, 1)))
        p.wait()
        cortes = sorted(set(cortes))
        st("Ritmo", "Calculando a duração dos planos…", 90)
        pontos = [0.0] + cortes + [dur]
        planos = [b - a for a, b in zip(pontos, pontos[1:]) if b - a > 0.2]
        if not planos:
            raise RuntimeError("não encontrei planos nesse vídeo")
        analise = {"duracao": round(dur, 1), "planos": len(planos), "media": round(statistics.mean(planos), 2),
                   "mediana": round(statistics.median(planos), 2), "menor": round(min(planos), 2),
                   "maior": round(max(planos), 2),
                   "cortes_por_min": round(len(cortes) / (dur / 60), 1) if dur else 0,
                   "planos_lista": [round(x, 2) for x in planos[:400]],
                   "curtos": sum(1 for x in planos if x < 2), "longos": sum(1 for x in planos if x > 6),
                   "quando": time.strftime("%d/%m/%Y %H:%M")}
        salvar_resultado(args.id, analise)
        msg = (f"{analise['planos']} plano(s) em {analise['duracao']:.0f} s · média {analise['media']} s · "
               f"{analise['cortes_por_min']} cortes/min")
        st("Concluído", msg, 100, fim=time.time())
    except Exception as e:  # noqa: BLE001
        st("Erro", str(e), st.d["pct"], erro=str(e), fim=time.time())
        sys.exit(1)


if __name__ == "__main__":
    main()
