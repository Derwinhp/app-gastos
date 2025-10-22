import streamlit as st
import pandas as pd
import sqlite3
import datetime
import plotly.express as px

# --- Configuración de la Base de Datos ---
DB_NAME = "gastos_personales.db"

def init_db():
    """Inicializa la base de datos y crea la tabla si no existe."""
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS gastos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                categoria TEXT NOT NULL,
                concepto TEXT NOT NULL,
                banco TEXT NOT NULL,
                monto_usd REAL NOT NULL, 
                fecha DATE NOT NULL
            );
        """)
        
        # --- Migraciones de versiones anteriores ---
        try:
            c.execute("ALTER TABLE gastos RENAME COLUMN monto TO monto_usd")
        except sqlite3.OperationalError:
            pass # La columna ya se llama monto_usd o la tabla es nueva
            
        try:
            c.execute("ALTER TABLE gastos ADD COLUMN categoria TEXT NOT NULL DEFAULT 'Otros'")
        except sqlite3.OperationalError:
            pass # La columna ya existe
            
        conn.commit()
    except sqlite3.Error as e:
        st.error(f"Error al inicializar la base de datos: {e}")
    finally:
        if conn:
            conn.close()

def guardar_gasto(categoria, concepto, banco, monto_usd, fecha):
    """Guarda un nuevo gasto en la base de datos (siempre en USD)."""
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        fecha_str = fecha.strftime('%Y-%m-%d')
        c.execute("INSERT INTO gastos (categoria, concepto, banco, monto_usd, fecha) VALUES (?, ?, ?, ?, ?)",
                  (categoria, concepto, banco, monto_usd, fecha_str))
        conn.commit()
        st.success(f"¡Gasto de {monto_usd:,.2f} USD en '{concepto}' ({categoria}) guardado!")
    except sqlite3.Error as e:
        st.error(f"Error al guardar el gasto: {e}")
    finally:
        if conn:
            conn.close()

@st.cache_data(ttl=60) # Cache para no leer la DB en cada re-render, se actualiza cada 60s
def cargar_datos():
    """Carga todos los gastos de la base de datos a un DataFrame de Pandas."""
    try:
        conn = sqlite3.connect(DB_NAME)
        df = pd.read_sql_query("SELECT id, categoria, concepto, banco, monto_usd, fecha FROM gastos ORDER BY fecha DESC", conn)
        if not df.empty:
            df['fecha'] = pd.to_datetime(df['fecha'])
        return df
    except Exception as e:
        st.error(f"Error al cargar los datos: {e}")
        return pd.DataFrame(columns=['id', 'categoria', 'concepto', 'banco', 'monto_usd', 'fecha'])
    finally:
        if conn:
            conn.close()

# --- NUEVAS FUNCIONES DE GESTIÓN ---

def actualizar_nombre_categoria(old_name, new_name):
    """Renombra una categoría en toda la base de datos."""
    if not new_name.strip():
        st.sidebar.error("El nuevo nombre no puede estar vacío.")
        return
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("UPDATE gastos SET categoria = ? WHERE categoria = ?", (new_name.strip(), old_name))
        conn.commit()
        st.sidebar.success(f"Categoría '{old_name}' renombrada a '{new_name}'!")
    except sqlite3.Error as e:
        st.sidebar.error(f"Error al actualizar: {e}")
    finally:
        if conn:
            conn.close()
    st.cache_data.clear()
    st.rerun()

def eliminar_gasto(gasto_id):
    """Elimina un gasto específico por su ID."""
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("DELETE FROM gastos WHERE id = ?", (gasto_id,))
        conn.commit()
        # Verificar si algo se eliminó
        if conn.total_changes == 0:
            st.sidebar.warning(f"No se encontró ningún gasto con ID {gasto_id}.")
        else:
            st.sidebar.success(f"Gasto con ID {gasto_id} eliminado.")
    except sqlite3.Error as e:
        st.sidebar.error(f"Error al eliminar: {e}")
    finally:
        if conn:
            conn.close()
    st.cache_data.clear()
    st.rerun()

# --- Configuración de la Página ---
st.set_page_config(page_title="Control de Gastos", layout="wide")

# --- Inicializar DB ---
init_db()

# --- Cargar Datos (Necesario ANTES del formulario para las categorías) ---
df_gastos = cargar_datos()

# --- NUEVO: Sidebar de Gestión ---
st.sidebar.title("🔧 Gestión de Datos")

with st.sidebar.expander("Renombrar Categoría"):
    if not df_gastos.empty:
        categorias_unicas = sorted(df_gastos['categoria'].unique().tolist())
        categoria_a_editar = st.selectbox("Categoría a renombrar", options=categorias_unicas, key="sb_cat_edit")
        nuevo_nombre = st.text_input("Nuevo nombre para la categoría", key="sb_cat_new")
        
        if st.button("Actualizar Categoría"):
            if categoria_a_editar != nuevo_nombre:
                actualizar_nombre_categoria(categoria_a_editar, nuevo_nombre)
            else:
                st.sidebar.warning("El nuevo nombre es igual al anterior.")
    else:
        st.sidebar.info("No hay categorías para editar.")

with st.sidebar.expander("Eliminar un Gasto"):
    id_a_eliminar = st.number_input("ID del gasto a eliminar", min_value=1, step=1, format="%d", help="El ID es visible en la tabla del historial al final de la página.", key="sb_id_del")
    
    if st.button("Eliminar Gasto", type="secondary"):
        eliminar_gasto(id_a_eliminar)

# --- Título de la App ---
st.title("📊 Aplicación de Control de Gastos con Categorías")
st.markdown("Registra tus gastos, clasifícalos por categorías y visualiza tus finanzas.")

# --- Formulario de Entrada ---
st.header("Añadir Nuevo Gasto")

# --- Lógica de Categorías Dinámicas ---
default_categorias = ["Alimentación", "Hogar", "Transporte", "Entretenimiento", "Salud", "Educación", "Otros"]
if not df_gastos.empty:
    categorias_existentes = df_gastos['categoria'].unique().tolist()
else:
    categorias_existentes = []
# Combinar y eliminar duplicados
opciones_categoria = sorted(list(set(default_categorias + categorias_existentes)))
opciones_finales = opciones_categoria + ["Otra (Crear Nueva)"]


# Usar columnas para un layout más limpio
col1, col2, col3 = st.columns(3)

with col1:
    categoria_seleccionada = st.selectbox("Categoría", 
                                          opciones_finales, 
                                          key='categoria_select',
                                          help="Elige una categoría o crea una nueva.")
    
    if categoria_seleccionada == "Otra (Crear Nueva)":
        categoria_final = st.text_input("Nombre Nueva Categoría", key='categoria_nueva_input')
    else:
        categoria_final = categoria_seleccionada
        
    concepto = st.text_input("Concepto del Gasto", placeholder="Ej: Supermercado, Cine, Gasolina")

with col2:
    banco = st.text_input("Banco o Método de Pago", placeholder="Ej: Banco A, Efectivo")
    monto_ingresado = st.number_input("Monto", min_value=0.01, format="%.2f")

with col3:
    moneda = st.selectbox("Moneda", ("USD $", "Bolívares Bs."), help="Selecciona la moneda en la que pagaste.")
    
    # --- Lógica Condicional para Tasa de Cambio ---
    tasa_cambio = 0
    if moneda == "Bolívares Bs.":
        tasa_cambio = st.number_input("Tasa de Cambio (Bs. por $)", 
                                      min_value=0.01, 
                                      format="%.4f", 
                                      help="¿Cuántos Bolívares cuesta 1 Dólar hoy?")
    
    fecha = st.date_input("Fecha del Gasto", datetime.date.today())

if st.button("Guardar Gasto", type="primary"):
    
    # --- Lógica de Conversión ---
    monto_final_usd = 0
    valid_input = True

    if not categoria_final or not concepto or not banco or monto_ingresado <= 0:
        st.warning("Por favor, completa todos los campos (Categoría, Concepto, Banco y Monto).")
        valid_input = False
    
    elif moneda == "Bolívares Bs.":
        if tasa_cambio <= 0:
            st.warning("Por favor, ingresa una Tasa de Cambio válida.")
            valid_input = False
        else:
            monto_final_usd = monto_ingresado / tasa_cambio
    
    elif moneda == "USD $":
        monto_final_usd = monto_ingresado
    
    # --- Guardar ---
    if valid_input:
        guardar_gasto(categoria_final.strip(), concepto, banco, monto_final_usd, fecha)
        # Limpiar el cache para que los datos se recarguen
        st.cache_data.clear()
        # Limpiar campos (opcional, pero mejora la usabilidad)
        st.rerun()

st.divider()


if df_gastos.empty:
    st.info("Aún no has registrado ningún gasto. ¡Empieza añadiendo uno!")
else:
    # --- Dashboard / Reportes Visuales ---
    st.header("📈 Reportes en Tiempo Real (Consolidado en USD)")

    # --- Métricas Principales ---
    col1, col2, col3 = st.columns(3)
    total_gastado = df_gastos['monto_usd'].sum()
    gasto_promedio = df_gastos['monto_usd'].mean()
    num_gastos = len(df_gastos)

    col1.metric("Gasto Total (USD)", f"{total_gastado:,.2f} $")
    col2.metric("Gasto Promedio (USD)", f"{gasto_promedio:,.2f} $")
    col3.metric("Número de Registros", f"{num_gastos}")

    st.markdown("---")

    # --- Gráficos ---
    col_graf1, col_graf2 = st.columns(2)

    with col_graf1:
        st.subheader("Gastos por Categoría (USD)")
        # Agrupar categorías, sumar montos y ordenar
        gastos_categoria = df_gastos.groupby('categoria')['monto_usd'].sum().nlargest(10).sort_values(ascending=False)
        if not gastos_categoria.empty:
            # Gráfico de pastel (pie chart) para ver la distribución
            fig_categoria = px.pie(gastos_categoria,
                                   values='monto_usd',
                                   names=gastos_categoria.index,
                                   title="Top 10 Gastos por Categoría",
                                   hole=.3) # Gráfico de dona
            fig_categoria.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig_categoria, use_container_width=True)
        else:
            st.info("No hay suficientes datos para el gráfico de categorías.")

    with col_graf2:
        st.subheader("Gastos por Banco (USD)")
        gastos_banco = df_gastos.groupby('banco')['monto_usd'].sum().sort_values(ascending=False)
        if not gastos_banco.empty:
            fig_banco = px.pie(gastos_banco,
                               values='monto_usd',
                               names=gastos_banco.index,
                               title="Distribución de Gastos por Banco",
                               hole=.3) # Gráfico de dona
            fig_banco.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig_banco, use_container_width=True)
        else:
            st.info("No hay suficientes datos para el gráfico de bancos.")

    st.subheader("Evolución de Gastos en el Tiempo (USD)")
    # Agrupar por día para ver la tendencia
    gastos_tiempo = df_gastos.set_index('fecha').resample('D')['monto_usd'].sum().reset_index()
    if not gastos_tiempo.empty:
        fig_tiempo = px.line(gastos_tiempo,
                             x='fecha',
                             y='monto_usd',
                             title="Gastos Diarios a lo largo del Tiempo",
                             markers=True,
                             labels={'fecha': 'Fecha', 'monto_usd': 'Monto Gastado (USD)'})
        st.plotly_chart(fig_tiempo, use_container_width=True)
    else:
        st.info("No hay suficientes datos para el gráfico de tiempo.")


    # --- Historial de Gastos (Tabla) ---
    st.divider()
    st.header("Historial Detallado de Gastos (Montos en USD)")

    # Mostrar el dataframe con formato
    st.dataframe(
        df_gastos.style.format({
            'monto_usd': '{:,.2f} $',
            'fecha': '{:%Y-%m-%d}'
        }),
        use_container_width=True,
        hide_index=True,
        column_config={
            # CAMBIO: Mostrar el ID para que el usuario pueda usarlo para eliminar
            "id": st.column_config.NumberColumn("ID"), 
            "monto_usd": st.column_config.NumberColumn("Monto (USD)"),
            "categoria": "Categoría",
            "concepto": "Concepto",
            "banco": "Banco",
            "fecha": "Fecha",
        }
    )