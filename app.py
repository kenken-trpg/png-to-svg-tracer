from io import BytesIO
from pathlib import Path
from subprocess import TimeoutExpired, run
import sys
from tempfile import TemporaryDirectory

from PIL import Image
import streamlit as st


st.set_page_config(page_title="PNG → SVG")
st.title("PNG → SVG")
st.write("ロゴやイラストの輪郭をトレースし、拡大できるSVGに変換します。")
upload = st.file_uploader("PNG画像を選択（10 MiB以下）", type="png")
if upload is None:
    st.stop()

color = st.radio("カラーモード", ["カラー", "白黒"], horizontal=True)
preset = st.select_slider("描き込みの細かさ", ["シンプル", "標準", "高精細"], value="標準")
try:
    with Image.open(BytesIO(upload.getvalue()), formats=["PNG"]) as source:
        if source.width * source.height > 16_000_000:
            raise ValueError("入力は1600万画素以下にしてください。")
        source.thumbnail((1600, 1600))
        rgba = source.convert("RGBA")
except (OSError, ValueError, Image.DecompressionBombError) as error:
    st.error(f"PNGを読み込めませんでした。{error}")
    st.stop()

st.image(rgba, caption="入力画像（長辺1600pxまで）")
if st.button("SVGに変換", type="primary"):
    with TemporaryDirectory() as directory:
        png = Path(directory) / "input.png"
        svg = Path(directory) / "output.svg"
        rgba.save(png)
        try:
            with st.spinner("輪郭をトレースしています…"):
                result = run([sys.executable, str(Path(__file__).with_name("trace.py")),
                              str(png), str(svg), color, preset], timeout=30)
            if result.returncode or not svg.is_file():
                st.error("変換できませんでした。画像を縮小して再度お試しください。")
            else:
                data = svg.read_bytes()
                st.image(data.decode("utf-8"), caption="SVGプレビュー")
                st.download_button(f"SVGをダウンロード（{len(data)/1024:.1f} KiB）",
                                   data, Path(upload.name).stem + ".svg",
                                   "image/svg+xml", on_click="ignore")
        except TimeoutExpired:
            st.warning("30秒で変換を停止しました。シンプル設定または小さい画像でお試しください。")
