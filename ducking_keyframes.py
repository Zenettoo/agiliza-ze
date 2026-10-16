"""Ducking por keyframes: cria uma timeline nova com a música e keyframes de volume no início e no fim de cada fala.

A fala vem do Whisper (faixa de voz). Na música, cada fala gera um keyframe de descida (início) e um de subida (fim).
Não mexe na timeline original: a timeline nova é importada a partir de um arquivo XML.

Uso:
  .venv/bin/python ducking_keyframes.py --musica 2 --voz 1 --nivel -12 [--timeline "Filme copy"]
"""
import argparse
import os
import sys
import time
from pathlib import Path
from xml.sax.saxutils import escape

os.environ.setdefault("PYTHONUTF8", "1")
BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
sys.path.append("/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules")
import silencios as SIL  # noqa: E402


def linear(db):
    return round(10 ** (db / 20), 5)


def xml_timeline(nome, arq_midia, nome_midia, dur_midia, src_in, dur_clipe, fps, keys, nivel_db):
    """XML (FCP 7) com uma faixa de áudio: a música e os keyframes de volume ('Audio Levels')."""
    quadros = []
    quadros.append((0, linear(0)))
    for a, b in keys:
        quadros.append((round(a * fps), linear(nivel_db)))
        quadros.append((round(b * fps), linear(0)))
    quadros = sorted(set(quadros))
    kf = "".join(f"<keyframe><when>{q}</when><value>{v}</value><interpolation>linear</interpolation></keyframe>"
                 for q, v in quadros)
    url = Path(arq_midia).as_uri()
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE xmeml>
<xmeml version="4">
<sequence id="sequencia">
<name>{escape(nome)}</name>
<duration>{dur_clipe}</duration>
<rate><timebase>{fps}</timebase><ntsc>FALSE</ntsc></rate>
<media><audio><numOutputChannels>2</numOutputChannels>
<format><samplecharacteristics><depth>16</depth><samplerate>48000</samplerate></samplecharacteristics></format>
<track>
<clipitem id="musica">
<name>{escape(nome_midia)}</name>
<duration>{dur_midia}</duration>
<rate><timebase>{fps}</timebase><ntsc>FALSE</ntsc></rate>
<start>0</start><end>{dur_clipe}</end>
<in>{src_in}</in><out>{src_in + dur_clipe}</out>
<file id="arquivo"><name>{escape(nome_midia)}</name><pathurl>{escape(url)}</pathurl>
<rate><timebase>{fps}</timebase><ntsc>FALSE</ntsc></rate><duration>{dur_midia}</duration>
<media><audio><samplecharacteristics><depth>16</depth><samplerate>48000</samplerate></samplecharacteristics><channelcount>2</channelcount></audio></media></file>
<sourcetrack><mediatype>audio</mediatype><trackindex>1</trackindex></sourcetrack>
<filter><effect><name>Audio Levels</name><effectid>audiolevels</effectid><effectcategory>audiolevels</effectcategory>
<effecttype>audiolevels</effecttype><mediatype>audio</mediatype>
<parameter><parameterid>level</parameterid><name>Level</name><valuemin>0</valuemin><valuemax>3.98</valuemax><value>1</value>
{kf}
</parameter></effect></filter>
</clipitem>
</track></audio></media></sequence></xmeml>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--musica", type=int, required=True)
    ap.add_argument("--voz", type=int, required=True)
    ap.add_argument("--nivel", type=float, default=-12.0)
    ap.add_argument("--timeline", default=None, help="nome da timeline de origem (padrão: a aberta)")
    args = ap.parse_args()
    import DaVinciResolveScript as d  # noqa: N813
    r = d.scriptapp("Resolve")
    proj = r.GetProjectManager().GetCurrentProject()
    tl = None
    for i in range(1, proj.GetTimelineCount() + 1):
        t = proj.GetTimelineByIndex(i)
        if (args.timeline and t.GetName() == args.timeline) or (not args.timeline and t.GetName() == proj.GetCurrentTimeline().GetName()):
            tl = t
            break
    if not tl:
        raise SystemExit("timeline de origem não encontrada")
    tfps = float(tl.GetSetting("timelineFrameRate"))
    t0 = tl.GetStartFrame()
    musica = tl.GetItemListInTrack("audio", args.musica) or []
    voz = tl.GetItemListInTrack("audio", args.voz) or []
    if len(musica) != 1:
        raise SystemExit(f"a faixa A{args.musica} precisa ter um clipe de música só (tem {len(musica)})")
    it = musica[0]
    m = it.GetMediaPoolItem()
    arq = m.GetClipProperty("File Path")
    dur_clipe = int(it.GetDuration())
    fs, dur = SIL.falas(tl, voz, tfps)
    keys = [(max(0.0, a), max(0.0, b)) for a, b in fs]
    # agrupa palavras em falas contínuas (pausa menor que 0,6 s = mesma fala)
    falas = []
    for a, b in keys:
        if falas and a - falas[-1][1] < 0.6:
            falas[-1][1] = max(falas[-1][1], b)
        else:
            falas.append([a, b])
    falas = [(a, b) for a, b in falas if b > a]
    print(f"{len(falas)} fala(s) encontrada(s)")
    xml = xml_timeline(f"Ducking keyframes · {tl.GetName()}", arq, m.GetClipProperty("Clip Name") or Path(arq).name,
                       int(m.GetClipProperty("Frames") or dur_clipe), int(it.GetSourceStartFrame()), dur_clipe,
                       int(round(tfps)), falas, args.nivel)
    saida = BASE / "projetos" / "_sync" / f"ducking_keyframes_{time.strftime('%Y%m%d_%H%M%S')}.xml"
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(xml, encoding="utf-8")
    nova = proj.GetMediaPool().ImportTimelineFromFile(str(saida))
    print("timeline importada:", nova.GetName() if nova else "FALHOU")


if __name__ == "__main__":
    main()
