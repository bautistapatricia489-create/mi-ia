"""
Mi IA - versión para compartir con amigos (Streamlit Community Cloud)
- Tus amigos NO ponen clave de Gemini: la app usa la tuya, guardada en "Secrets".
- Para entrar escriben un código de acceso que tú les das (también en "Secrets").
- Si no configuras Secrets, la app pide la clave de cada persona (modo normal).
- Los chats viven solo en la sesión de cada visitante: son privados y no se guardan.
"""
import base64
import hmac
from datetime import datetime

import streamlit as st
from google import genai
from google.genai import types

# ======================= CONFIGURACIÓN =======================
NOMBRE_IA = "Mi IA"
ICONO = "🤖"
PERSONALIDAD_BASE = (
    "Eres un asistente amable, claro y honesto. "
    "Respondes en el idioma del usuario, con respuestas bien organizadas. "
    "Si no sabes algo, lo dices. Si el usuario adjunta archivos, los analizas con cuidado."
)
MODELOS = {
    "Gemini 3.8 Flash (recomendado)": "gemini-3.8-flash",
    "Gemini 3.5 Flash-Lite (más rápido)": "gemini-3.5-flash-lite",
}
MAX_MB = 5
IMAGENES = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
            "gif": "image/gif", "webp": "image/webp"}

st.set_page_config(page_title=NOMBRE_IA, page_icon=ICONO, layout="centered")


# ======================= SECRETS (tu clave y tu código, fuera del código) =======================
def secreto(nombre):
    try:
        return st.secrets[nombre]
    except Exception:
        return None


CLAVE_DUENO = secreto("GEMINI_API_KEY")
CODIGO_ACCESO = secreto("CODIGO_ACCESO")


# ======================= UTILIDADES =======================
def construir_partes(texto, archivos):
    partes = []
    for f in archivos or []:
        datos = f.getvalue()
        if len(datos) > MAX_MB * 1024 * 1024:
            st.warning(f"'{f.name}' pesa más de {MAX_MB} MB y no se envió.")
            continue
        ext = f.name.lower().rsplit(".", 1)[-1]
        if ext in IMAGENES or ext == "pdf":
            partes.append({"tipo": "archivo", "nombre": f.name,
                           "mime": IMAGENES.get(ext, "application/pdf"),
                           "data": base64.b64encode(datos).decode()})
        else:
            contenido = datos.decode("utf-8", errors="ignore")
            partes.append({"tipo": "texto",
                           "texto": f"[Archivo: {f.name}]\n{contenido}"})
    partes.append({"tipo": "texto", "texto": texto or "Analiza lo que te adjunté."})
    return partes


def a_contenidos(mensajes):
    contenidos = []
    for m in mensajes:
        partes = []
        for p in m["partes"]:
            if p["tipo"] == "texto":
                partes.append(types.Part.from_text(text=p["texto"]))
            else:
                partes.append(types.Part.from_bytes(
                    data=base64.b64decode(p["data"]), mime_type=p["mime"]))
        contenidos.append(types.Content(
            role="user" if m["role"] == "user" else "model", parts=partes))
    return contenidos


def mostrar_mensaje(m):
    with st.chat_message(m["role"], avatar=ICONO if m["role"] == "assistant" else None):
        for p in m["partes"]:
            if p["tipo"] == "texto":
                if p["texto"].startswith("[Archivo:"):
                    st.caption("📎 " + p["texto"].split("\n", 1)[0][1:-1])
                else:
                    st.markdown(p["texto"])
            elif p["mime"].startswith("image/"):
                st.image(base64.b64decode(p["data"]), width=300)
            else:
                st.caption("📄 " + p["nombre"])


# ======================= ESTADO (privado de cada visitante) =======================
if "mensajes" not in st.session_state:
    st.session_state.mensajes = []

# ======================= BARRA LATERAL =======================
with st.sidebar:
    st.title(f"{ICONO} {NOMBRE_IA}")
    if CLAVE_DUENO:
        api_key = CLAVE_DUENO
        if CODIGO_ACCESO and not st.session_state.get("acceso_ok"):
            codigo = st.text_input("Código de acceso", type="password",
                                   help="Te lo dio el dueño de esta IA.")
            if codigo and hmac.compare_digest(str(codigo), str(CODIGO_ACCESO)):
                st.session_state.acceso_ok = True
                st.rerun()
            if codigo:
                st.error("Código incorrecto.")
    else:
        api_key = st.text_input(
            "Tu API key de Gemini", type="password",
            help="Gratis en aistudio.google.com/apikey. No se guarda: solo se usa mientras la página está abierta.")
        st.caption("🔑 Consigue tu clave gratis en aistudio.google.com/apikey")

    if st.button("➕ Nuevo chat", use_container_width=True):
        st.session_state.mensajes = []
        st.rerun()

    with st.expander("⚙️ Ajustes"):
        modelo_nombre = st.selectbox("Modelo", list(MODELOS))
        personalidad = st.text_area("Personalidad", PERSONALIDAD_BASE, height=150)
        buscar_web = st.checkbox("🌐 Buscar en internet", value=False)

    st.caption("🔒 Tus chats son privados y no se guardan: si recargas la página, se borran.")

if CLAVE_DUENO and CODIGO_ACCESO and not st.session_state.get("acceso_ok"):
    st.info("👈 Escribe el código de acceso en la barra lateral para empezar.")
    st.stop()

if not api_key:
    st.info("👈 Pega tu API key de Gemini en la barra lateral para empezar.")
    st.stop()

client = genai.Client(api_key=api_key)

# ======================= PANTALLA DE CHAT =======================
st.title(f"{ICONO} {NOMBRE_IA}")
if not st.session_state.mensajes:
    st.caption("Escríbeme algo o adjunta una imagen, un PDF o un archivo de texto.")

for m in st.session_state.mensajes:
    mostrar_mensaje(m)

entrada = st.chat_input(
    "Escribe tu mensaje...",
    accept_file="multiple",
    file_type=list(IMAGENES) + ["pdf", "txt", "md", "csv", "json", "py"],
)

if entrada:
    mensajes = st.session_state.mensajes
    mensaje_usuario = {"role": "user", "partes": construir_partes(entrada.text, entrada.files)}
    mensajes.append(mensaje_usuario)
    mostrar_mensaje(mensaje_usuario)

    config = types.GenerateContentConfig(
        system_instruction=personalidad + f"\nFecha de hoy: {datetime.now():%d/%m/%Y}.",
        tools=[types.Tool(google_search=types.GoogleSearch())] if buscar_web else None,
    )

    def generar():
        for trozo in client.models.generate_content_stream(
            model=MODELOS[modelo_nombre],
            contents=a_contenidos(mensajes),
            config=config,
        ):
            if trozo.text:
                yield trozo.text

    with st.chat_message("assistant", avatar=ICONO):
        try:
            respuesta = st.write_stream(generar())
            mensajes.append({"role": "assistant", "partes": [{"tipo": "texto", "texto": respuesta}]})
            st.rerun()
        except Exception as e:
            mensajes.pop()
            msg = str(e)
            if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                st.error("Llegaste al límite gratis por ahora. Espera un minuto e inténtalo otra vez.")
            elif "503" in msg or "UNAVAILABLE" in msg:
                st.error("Google está saturado. Cambia de modelo en Ajustes o inténtalo en un rato.")
            elif "API key" in msg or "401" in msg or "403" in msg or "400" in msg:
                st.error("La API key no es válida. Revísala e inténtalo de nuevo.")
            else:
                st.error(f"Ocurrió un error: {msg}")
