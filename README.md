# Supervisión Aloma — Dashboard

## Estructura del proyecto

```
aloma/
├── app.py                          ← Entry point: python app.py
├── config.py                       ← Rutas y constantes
│
├── data_files/                     ← ⚠️  ACÁ VAN LOS DATOS MENSUALES
│   ├── 2024-12/
│   │   ├── visitas/                ← .xlsx de visitas de diciembre 2024
│   │   ├── ventas/                 ← .xlsx de ventas de diciembre 2024
│   │   └── exhibiciones/           ← .xlsx de exhibiciones (opcional)
│   ├── 2025-01/
│   │   ├── visitas/
│   │   ├── ventas/
│   │   └── exhibiciones/
│   └── YYYY-MM/                    ← agregar carpeta por cada mes nuevo
│
├── master/
│   └── vendedores.xlsx             ← ⚠️  MAESTRO DE VENDEDORES
│
├── altas/
│   └── *.xlsx                      ← ⚠️  ARCHIVOS DE ALTAS DE CLIENTES
│
├── control_clientes_inactivos.xlsx ← ⚠️  INACTIVOS (en la raíz del proyecto)
│
├── data/
│   ├── loaders.py                  ← Carga de archivos Excel
│   └── cache.py                    ← Cache global + jornada precalculada
│
├── logic/
│   ├── kpis.py                     ← KPIs, jornada, ventas semanales
│   ├── mix.py                      ← Objetivo mix Corona
│   ├── rankings.py                 ← Rankings comparativos
│   └── resumen.py                  ← Resumen por vendedor + render cards
│
├── ui/
│   ├── styles.py                   ← Constantes visuales (colores, tablas)
│   ├── components.py               ← Componentes reutilizables (panel, kpi_card, etc.)
│   ├── layout.py                   ← app.layout completo
│   └── callbacks/
│       ├── __init__.py
│       ├── dashboard.py            ← Callbacks tab Dashboard
│       ├── rankings.py             ← Callbacks tab Rankings
│       └── resumen.py              ← Callbacks tab Resumen por Vendedor
│
└── utils/
    └── helpers.py                  ← Funciones utilitarias puras


## Para agregar un mes nuevo

1. Crear carpeta:  data_files/YYYY-MM/
2. Dentro crear:   visitas/  ventas/  exhibiciones/  (solo las que tengas)
3. Pegar los .xlsx correspondientes en cada subcarpeta
4. Hacer click en "↺ Recargar datos" en el dashboard


## Instalación

pip install dash pandas plotly openpyxl


## Ejecutar

python app.py
```
