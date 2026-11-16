import streamlit as st

st.set_page_config(page_title="Olist · Gestión y dashboard", page_icon="📦", layout="wide")

pagina = st.navigation(
    [
        st.Page("vistas/dashboard.py", title="Dashboard", icon="📊", default=True),
        st.Page("vistas/operaciones.py", title="Operaciones", icon="📦"),
    ]
)
pagina.run()
