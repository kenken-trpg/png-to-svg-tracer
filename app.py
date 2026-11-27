import logging
from pathlib import Path
from subprocess import TimeoutExpired, run
import sys
from tempfile import TemporaryDirectory
from threading import BoundedSemaphore

import streamlit as st

from limits import MAX_OUTPUT, MAX_UPLOAD, TIMEOUT


@st.cache_resource
def conversion_slot():
    return BoundedSemaphore(1)


def convert(upload, color, preset):
    slot = conversion_slot()
    if not slot.acquire(blocking=False):
        st.warning("別の画像を変換中です。少し待ってから再度お試しください。")
        return
    try:
        with TemporaryDirectory() as temp:
            directory = Path(temp)
            (directory / "input.png").write_bytes(upload.getbuffer())
            result = run([sys.executable, str(Path(__file__).resolve().with_name("trace.py")),
                          temp, color, preset], timeout=TIMEOUT)
            errors = {
                2: "入力は10 MiB・1,600万画素以下にしてください。",
                3: "PNGを読み込めませんでした。画像をPNG形式で保存し直してください。",
                4: "SVGが4 MiBの出力上限に達しました。シンプル設定か小さい画像をお試しください。",
            }
            if result.returncode:
                logging.warning("Conversion worker exit code: %s", result.returncode)
                st.error(errors.get(result.returncode, f"変換処理が停止しました（終了コード {result.returncode}）。管理者はCloud logsをご確認ください。"))
                return
            svg = directory / "output.svg"
            if svg.stat().st_size >= MAX_OUTPUT:
                st.error(errors[4])
                return
            return (directory / "preview.png").read_bytes(), svg.read_bytes()
    except TimeoutExpired:
        st.warning("30秒で処理を停止しました。長辺512 px以下でお試しください。")
    finally:
        slot.release()


st.set_page_config(page_title="PNG → SVG")
st.title("PNG → SVG")
st.write("ロゴやイラストの輪郭をトレースし、拡大できるSVGに変換します。")
st.caption("Community Cloudでは、まず少色のロゴで長辺256〜512 px・標準をお試しください。長辺1,024 pxを超える入力は縮小します。")
upload = st.file_uploader("PNG画像を選択（10 MiB以下）", type="png")
if upload is None:
    st.stop()
if upload.size > MAX_UPLOAD:
    st.error("10 MiB以下のPNGを選んでください。")
    st.stop()
color = st.radio("カラーモード", ["カラー", "白黒"], horizontal=True)
preset = st.select_slider("描き込みの細かさ", ["シンプル", "標準", "高精細"], value="標準")
if st.button("SVGに変換", type="primary"):
    with st.spinner("画像を確認して輪郭をトレースしています…"):
        output = convert(upload, color, preset)
    if output:
        preview, svg = output
        st.image(preview, caption="トレースに使用した入力画像")
        st.image(svg.decode("utf-8"), caption="SVGプレビュー")
        st.download_button(f"SVGをダウンロード（{len(svg)/1024:.1f} KiB）", svg,
                           Path(upload.name).stem + ".svg", "image/svg+xml", on_click="ignore")
