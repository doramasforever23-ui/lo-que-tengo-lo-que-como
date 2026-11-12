"""Lo que tengo, lo que como: menús equilibrados con lo que hay en tu nevera.
Ejecutar con:  streamlit run app.py
"""
from pathlib import Path

import pandas as pd
import streamlit as st

# ---------------------------------------------------------------- DATOS Y REGLAS
CSV = Path(__file__).with_name("alimentos.csv")

GRUPOS = {  # clave: (nombre, color)
    "carb": ("Carbohidratos", "#C98F1E"),
    "prot": ("Proteínas", "#C2503B"),
    "fruit": ("Frutas", "#B23C84"),
    "veg": ("Vegetales", "#3B8A4C"),
    "fat": ("Grasas saludables", "#3C78AD"),
}
# kcal extra por 100 g que aporta el aceite o la grasa de cada preparación (aproximado)
COCCION_KCAL = {"crudo": 0, "tal cual": 0, "hervido": 0, "al vapor": 0, "tostado": 0,
                "a la plancha": 20, "al horno": 20, "revuelto": 30, "salteado": 45, "frito": 110}
NEUTRO = {"tal cual", "crudo"}
ACTIVIDAD = {"Sedentaria (casi sin ejercicio)": 1.2, "Ligera (1 a 3 días por semana)": 1.375,
             "Moderada (3 a 5 días por semana)": 1.55, "Alta (6 a 7 días por semana)": 1.725}
OBJETIVO = {"Bajar de peso": -0.15, "Mantener mi peso": 0.0, "Ganar masa o peso": 0.10}
REPARTO = {"Desayuno": .25, "Almuerzo": .35, "Merienda": .10, "Cena": .30}
RECETA = {  # qué parte de las calorías de la comida aporta cada grupo
    "Desayuno": {"carb": .40, "prot": .35, "fruit": .25},
    "Almuerzo": {"carb": .38, "prot": .32, "veg": .15, "fat": .15},
    "Merienda": {"fruit": .60, "fat": .40},
    "Cena": {"carb": .38, "prot": .32, "veg": .15, "fat": .15},
}
DESAYUNO = {"Avena", "Huevo", "Pan integral", "Verde", "Choclo", "Queso fresco", "Yogur natural", "Leche"}
SOLO_DESAYUNO = {"Avena", "Yogur natural", "Leche"}
LEGUMBRES = {"Lentejas", "Frejol", "Garbanzo"}
MEDIDAS = {  # medidas caseras para alimentos que agrega la persona: nombre -> (texto, gramos típicos)
    "taza": ("taza|tazas", 150), "unidad mediana": ("unidad mediana|unidades medianas", 120),
    "cucharada": ("cucharada|cucharadas", 12), "puñado": ("puñado|puñados", 28),
    "rebanada": ("rebanada|rebanadas", 30), "porción": ("porción|porciones", 100)}
KCAL_GRUPO = {"carb": 130, "prot": 150, "fruit": 50, "veg": 30, "fat": 300}


@st.cache_data
def cargar_base() -> pd.DataFrame:
    """Lee la base de datos de alimentos con pandas."""
    return pd.read_csv(CSV)


def base_completa() -> pd.DataFrame:
    """Base del CSV más los alimentos que agregó la persona."""
    extra = pd.DataFrame(st.session_state.get("custom", []), columns=cargar_base().columns)
    return pd.concat([cargar_base(), extra], ignore_index=True)


# ---------------------------------------------------------------- CÁLCULOS
def calcular_necesidades(edad, sexo, peso, talla, actividad, objetivo) -> dict:
    """Fórmula de Mifflin-St Jeor + factor de actividad + objetivo."""
    bmr = 10 * peso + 6.25 * talla - 5 * edad + (5 if sexo == "Hombre" else -161)
    minimo = 1500 if sexo == "Hombre" else 1200
    kcal = max(round(bmr * ACTIVIDAD[actividad] * (1 + OBJETIVO[objetivo])), minimo)
    prot = round(peso * (1.6 if OBJETIVO[objetivo] > 0 else 1.2))
    grasa = round(kcal * 0.28 / 9)
    carb = round((kcal - prot * 4 - grasa * 9) / 4)
    return {"kcal": kcal, "prot": prot, "carb": carb, "grasa": grasa, "agua": round(peso * 0.035, 1)}


def construir_despensa(base: pd.DataFrame) -> pd.DataFrame:
    """Filtra lo que la persona tiene y agrega cómo lo prepara."""
    filas = []
    for g in GRUPOS:
        for alimento in st.session_state.get(f"sel_{g}", []):
            fila = base[base.alimento == alimento].iloc[0].copy()
            fila["coccion"] = st.session_state.get(f"coc_{alimento}", fila.cocciones.split("|")[0])
            fila["kcal_ef"] = fila.kcal_100g + COCCION_KCAL.get(fila.coccion, 0)
            filas.append(fila)
    return pd.DataFrame(filas)


def cantidad(n: float) -> str:
    entero = int(n)
    if entero == 0:
        return "½"
    return f"{entero} ½" if n - entero >= 0.5 else str(entero)


def adjetivo(alimento: str, coccion: str) -> str:
    if alimento == "Carne de res" and coccion.endswith("o") and not coccion.startswith("al "):
        return coccion[:-1] + "a"
    return coccion


def con_coccion(fila) -> str:
    return fila.alimento if fila.coccion in NEUTRO else f"{fila.alimento} {adjetivo(fila.alimento, fila.coccion)}"


def nombre_plato(comida: str, e: dict) -> str:
    p, c, v, f, fa = (e.get(k) for k in ("prot", "carb", "veg", "fruit", "fat"))
    cap = lambda s: s[:1].upper() + s[1:]
    if comida == "Merienda":
        return cap(" con ".join(x.alimento.lower() for x in (f, fa) if x is not None)) or "Fruta"
    partes = []
    if p is not None and p.alimento in LEGUMBRES:
        partes.append(f"Guiso de {p.alimento.lower()}")
    elif p is not None:
        partes.append(con_coccion(p))
    if c is not None:
        partes.append(("con " if partes else "") + c.alimento.lower())
    if v is not None:
        partes.append(("y ensalada de " if partes else "Ensalada de ") + v.alimento.lower())
    if f is not None:
        partes.append(("y " if partes else "") + f.alimento.lower())
    return cap(" ".join(partes))


def armar_comida(nombre: str, dia: int, semilla: int, kcal_dia: int, despensa: pd.DataFrame) -> dict:
    meta = kcal_dia * REPARTO[nombre]
    escogidos, items = {}, []
    for i, (grupo, parte) in enumerate(RECETA[nombre].items()):
        sub = despensa[despensa.grupo == grupo] if len(despensa) else despensa
        if sub.empty:
            continue
        if nombre == "Desayuno":
            pref = sub[sub.alimento.isin(DESAYUNO)]
            sub = pref if len(pref) else sub
        elif nombre == "Merienda":
            sub = sub[sub.alimento != "Aceite de oliva"]
        else:
            otros = sub[~sub.alimento.isin(SOLO_DESAYUNO)]
            sub = otros if len(otros) else sub
        if sub.empty:
            continue
        fila = sub.iloc[(dia + semilla + i + len(nombre)) % len(sub)]
        kcal_medida = fila.kcal_ef * fila.g_medida / 100
        if grupo == "fat" or fila.alimento == "Huevo":  # cantidades enteras (cucharadas, puñados, huevos)
            n = min(max(round(meta * parte / kcal_medida), 1), 2 if grupo == "fat" else 3)
        else:
            minimo, maximo = (1, 2) if grupo == "veg" else (0.5, 3)
            n = min(max(round(meta * parte / kcal_medida * 2) / 2, minimo), maximo)
        sing, plur = fila.medida.split("|")
        medida = sing if n <= 1 else plur
        if sing.lower() == fila.alimento.lower():  # ej.: "2 huevos"
            texto = f"{cantidad(n)} {medida}"
        else:
            texto = f"{cantidad(n)} {medida} de {fila.alimento.lower()}"
        if fila.coccion not in NEUTRO:
            texto += f" ({fila.coccion})"
        items.append({"texto": texto, "kcal": round(n * kcal_medida), "color": GRUPOS[grupo][1]})
        escogidos[grupo] = fila
    return {"nombre": nombre, "plato": nombre_plato(nombre, escogidos) if escogidos else "",
            "items": items, "kcal": sum(x["kcal"] for x in items), "meta": round(meta)}


def mostrar_comida(c: dict):
    with st.container(border=True):
        st.markdown(f"#### {c['nombre']}")
        if not c["items"]:
            st.caption("Agrega alimentos de los grupos que faltan para completar esta comida.")
            return
        st.caption(f"≈ {c['kcal']} kcal de {c['meta']} sugeridas")
        st.markdown(f"**{c['plato']}**")
        for it in c["items"]:
            st.markdown(f"<span style='color:{it['color']}'>●</span> {it['texto']} · {it['kcal']} kcal",
                        unsafe_allow_html=True)


# ---------------------------------------------------------------- ALIMENTO PROPIO
def agregar_alimento():
    s = st.session_state
    nombre = s.get("n_nombre", "").strip().capitalize()
    if not nombre:
        s["msg_custom"] = "Escribe el nombre del alimento."
        return
    base = base_completa()
    if nombre.lower() in base.alimento.str.lower().values:
        s["msg_custom"] = f"{nombre} ya está en la lista."
        return
    g = s["n_grupo"]
    texto_medida, g_tipico = MEDIDAS[s["n_medida"]]
    s.setdefault("custom", []).append({
        "alimento": nombre, "grupo": g,
        "kcal_100g": s["n_kcal"] or KCAL_GRUPO[g],
        "medida": texto_medida, "g_medida": s["n_gramos"] or g_tipico,
        "cocciones": "crudo" if g == "fruit" else "tal cual|hervido|al horno|a la plancha|salteado|frito"})
    s[f"sel_{g}"] = list(s.get(f"sel_{g}", [])) + [nombre]
    s["n_nombre"] = ""
    s["msg_custom"] = f"{nombre} agregado y seleccionado."


# ---------------------------------------------------------------- INTERFAZ
CSS = """<style>
@import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:wght@600;800&display=swap');
h1,h2,h3,h4{font-family:'Bricolage Grotesque',sans-serif!important;letter-spacing:-.02em}
.hero{font:800 clamp(2.2rem,5vw,3.6rem)/1.05 'Bricolage Grotesque',sans-serif;margin:.2rem 0}
.sub{opacity:.75;font-size:1.05rem}
.plato{width:130px;height:130px;border-radius:50%;margin-left:auto;
background:conic-gradient(#3B8A4C 0 33%,#B23C84 33% 50%,#C98F1E 50% 75%,#C2503B 75%);
box-shadow:0 0 0 7px rgba(128,128,128,.14)}
</style>"""


def main():
    st.set_page_config(page_title="Lo que tengo, lo que como", page_icon="🥗", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    st.session_state.setdefault("semilla", 0)

    with st.sidebar:
        st.header("Tu perfil")
        edad = st.number_input("Edad (años)", 1, 110, 30)
        sexo = st.radio("Sexo", ["Mujer", "Hombre"], horizontal=True)
        peso = st.number_input("Peso (kg)", 10.0, 300.0, 68.0)
        talla = st.number_input("Estatura (cm)", 80, 230, 168)
        actividad = st.selectbox("Actividad física", list(ACTIVIDAD))
        objetivo = st.selectbox("Objetivo", list(OBJETIVO))
    needs = calcular_necesidades(edad, sexo, peso, talla, actividad, objetivo)
    if edad < 18:
        needs["kcal"] = 2000

    col1, col2 = st.columns([4, 1])
    col1.markdown("<div class='hero'>Lo que tengo, lo que como</div>"
                  "<div class='sub'>Dinos qué hay en tu nevera y armamos menús equilibrados con eso.</div>",
                  unsafe_allow_html=True)
    col2.markdown("<div class='plato'></div>", unsafe_allow_html=True)

    t_metas, t_nevera, t_menu, t_fuentes = st.tabs(["Mis metas", "Mi nevera", "Mi menú", "Fuentes y datos"])
    base = base_completa()

    with t_metas:
        if edad < 18:
            st.warning("Las necesidades de niños y adolescentes dependen del crecimiento. "
                       "Consulta a un pediatra o nutricionista. Los menús usan 2000 kcal de referencia.")
        else:
            a, b, c, d = st.columns(4)
            a.metric("Calorías al día", f"{needs['kcal']} kcal")
            b.metric("Proteínas", f"{needs['prot']} g")
            c.metric("Carbohidratos", f"{needs['carb']} g")
            d.metric("Grasas", f"{needs['grasa']} g")
            st.write(f"Agua: unos {needs['agua']} L al día. Frutas y verduras: al menos 400 g. "
                     "Sal: menos de 5 g. Azúcares libres: menos del 10 % de tus calorías (OMS).")

    with t_nevera:
        st.write("Elige lo que tienes y cómo lo preparas. Las cantidades del menú saldrán en tazas, "
                 "unidades y cucharadas.")
        for g, (nombre_g, color) in GRUPOS.items():
            st.markdown(f"<h4 style='color:{color}'>{nombre_g}</h4>", unsafe_allow_html=True)
            elegidos = st.multiselect(nombre_g, sorted(base[base.grupo == g].alimento),
                                      key=f"sel_{g}", label_visibility="collapsed")
            cols = st.columns(3)
            for i, alimento in enumerate(elegidos):
                opciones = base[base.alimento == alimento].iloc[0].cocciones.split("|")
                cols[i % 3].selectbox(f"¿Cómo preparas {alimento.lower()}?", opciones, key=f"coc_{alimento}")

        with st.expander("¿Tienes otro alimento en casa? Agrégalo"):
            with st.form("nuevo", clear_on_submit=False):
                st.text_input("Nombre", key="n_nombre", placeholder="Ej.: Mote, Cebada, Chocho")
                x, y = st.columns(2)
                x.selectbox("Grupo", list(GRUPOS), format_func=lambda k: GRUPOS[k][0], key="n_grupo")
                y.selectbox("¿En qué medida lo comes?", list(MEDIDAS), key="n_medida")
                z, w = st.columns(2)
                z.number_input("kcal por 100 g (0 = promedio del grupo)", 0, 900, 0, key="n_kcal")
                w.number_input("Gramos por medida (0 = valor típico)", 0, 1000, 0, key="n_gramos")
                st.form_submit_button("Agregar", on_click=agregar_alimento)
            if st.session_state.get("msg_custom"):
                st.info(st.session_state["msg_custom"])

    despensa = construir_despensa(base)

    with t_menu:
        if despensa.empty:
            st.info("Elige algunos alimentos en la pestaña Mi nevera y tu menú aparecerá aquí.")
        else:
            faltan = [GRUPOS[g][0].lower() for g in GRUPOS if g not in set(despensa.grupo)]
            if faltan:
                st.warning("Para un menú más completo te faltan: " + ", ".join(faltan) + ".")
            k, _ = st.columns([1, 3])
            k.button("Generar otro menú", on_click=lambda: st.session_state.update(semilla=st.session_state.semilla + 1))
            modo = st.radio("Tipo de menú", ["Un día", "Una semana"], horizontal=True, label_visibility="collapsed")
            semilla = st.session_state.semilla
            if modo == "Un día":
                comidas = [armar_comida(n, 0, semilla, needs["kcal"], despensa) for n in REPARTO]
                for fila in (comidas[:2], comidas[2:]):
                    for col, c in zip(st.columns(2), fila):
                        with col:
                            mostrar_comida(c)
            else:
                dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
                for i, tab in enumerate(st.tabs(dias)):
                    with tab:
                        comidas = [armar_comida(n, i, semilla, needs["kcal"], despensa) for n in REPARTO]
                        for fila in (comidas[:2], comidas[2:]):
                            for col, c in zip(st.columns(2), fila):
                                with col:
                                    mostrar_comida(c)

    with t_fuentes:
        st.markdown(
            "- [OMS: alimentación sana](https://www.who.int/news-room/fact-sheets/detail/healthy-diet): "
            "frutas y verduras (400 g o más), grasas (menos del 30 % de la energía), azúcares libres y sal.\n"
            "- [Guías Alimentarias del Ecuador, MSP y FAO](https://www.fao.org/3/ca9928es/ca9928es.pdf)\n"
            "- [Mifflin y otros (1990)](https://doi.org/10.1093/ajcn/51.2.241): calorías en reposo.\n"
            "- [USDA FoodData Central](https://fdc.nal.usda.gov/): referencia de calorías por alimento.")
        st.caption("Las calorías, las medidas caseras y el aporte de aceite al freír son aproximados. "
                   "Las metas de proteína y grasa son criterios de este proyecto. Es una guía general para "
                   "adultos y no reemplaza a un nutricionista.")
        st.subheader("Base de datos (pandas)")
        st.dataframe(base, use_container_width=True, hide_index=True)
        st.download_button("Descargar alimentos.csv", base.to_csv(index=False), "alimentos.csv", "text/csv")


if __name__ == "__main__":
    main()
