# Photo Editor — Studio futurista en Flask

Editor de fotografía web con cuatro patrones de diseño clásicos.

* **Flask** + **SQLAlchemy** + **SQLite** en el backend.
* **Pillow** para el renderizado de imagen.
* **Tailwind CSS v4** (CLI standalone) para los estilos.
* UI oscura, elegante y futurista inspirada en agencias modernas.

## Patrones implementados

| # | Patrón | Dónde vive | Para qué sirve aquí |
|---|--------|------------|--------------------|
| 1 | MVC (MTV) | `app/__init__.py`, `app/models.py`, `app/routes/*.py`, `app/templates/*.html` | Flask separa Model (SQLAlchemy), Template (Jinja) y View/Controller (blueprints). |
| 2 | Command | `app/patterns/command.py` | Cada acción (añadir forma, mover slider, clonar capa) se modela como un `Command` con `execute()` y `undo()`. Historia persistida en SQLite. |
| 3 | Decorator | `app/patterns/decorator.py` | Los filtros (brillo, contraste, sepia, blur, …) son decoradores encadenables sobre `ImageComponent`. |
| 4 | Prototype | `app/patterns/prototype.py` | `LayerPrototype.clone()` duplica capas con un offset, como copy/paste de Figma. |

## Cómo correrlo (macOS / Linux)

### 1. Backend

```bash
cd photo-editor
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Frontend (Tailwind v4 CLI)

```bash
npm install
npm run build:css        # build one-shot
# o para desarrollo:
npm run dev:css          # watcher
```

### 3. Arrancar la app

```bash
python run.py
# abre http://127.0.0.1:5000
```

## Atajos del editor

| Acción | Atajo |
|--------|-------|
| Undo | `⌘Z` / `Ctrl+Z` |
| Redo | `⌘⇧Z` / `Ctrl+Shift+Z` |
| Duplicar capa seleccionada | `⌘D` / `Ctrl+D` |
| Eliminar capa | `Backspace` / `Delete` |

## Estructura

```
photo-editor/
├── app/
│   ├── __init__.py            # Application factory (cablea MTV)
│   ├── extensions.py          # SQLAlchemy
│   ├── models.py              # Project, Layer, HistoryEntry
│   ├── routes/
│   │   ├── main.py            # vistas HTML (index, editor)
│   │   └── api.py             # endpoints JSON para los comandos
│   ├── services/
│   │   └── renderer.py        # composición final (Decorator + capas)
│   ├── patterns/
│   │   ├── prototype.py
│   │   ├── decorator.py
│   │   └── command.py
│   ├── static/
│   │   ├── css/{input.css,tailwind.css}
│   │   ├── js/editor.js
│   │   └── uploads/           # imágenes subidas
│   └── templates/{base,index,editor}.html
├── instance/photo_editor.sqlite3
├── requirements.txt
├── package.json
└── run.py
```
