# PDF Footer Editor

A local, privacy-focused PDF editor specifically designed for editing footer text in PDF documents.

## Features

- **Open & View PDFs**: Display PDF pages with zoom and navigation
- **Text Selection**: Click on any text to select and edit it
- **Footer Detection**: Automatically detect footer text at the bottom of pages
- **Text Replacement**: Replace text while preserving formatting
- **Batch Processing**: Apply changes to multiple pages at once
- **Export**: Save edited PDFs without modifying originals
- **Keyboard Shortcuts**: Ctrl+O (Open), Ctrl+S (Save), Ctrl+Z (Undo), Ctrl+Y (Redo)

## Quick Start

### Prerequisites

- Python 3.8 or higher
- pip

### Installation

1. Clone or download this project

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
python run.py
```

4. The application will open automatically at http://localhost:8000

## Usage

### Basic Workflow

1. Click **Open** or drag-and-drop a PDF file
2. Navigate pages using thumbnails or arrow buttons
3. Click on any text to select it
4. Edit the text in the right sidebar
5. Click **Apply** to save changes
6. Click **Export** to download the edited PDF

### Footer Editing Mode

1. Click **Footer Mode** in the toolbar
2. Footer text blocks will be highlighted in green
3. Click on footer text to edit
4. Choose to apply to current page, all pages, or a page range

### Batch Processing

1. Open a PDF
2. Select footer text
3. Enter new text
4. Select "All pages" or specify a page range
5. Click Apply

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl+O | Open PDF |
| Ctrl+S | Export PDF |
| Ctrl+Z | Undo |
| Ctrl+Y | Redo |
| Ctrl++ | Zoom In |
| Ctrl+- | Zoom Out |
| Esc | Cancel/Deselect |

## Project Structure

```
pdf-footer-editor/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI application
│   │   ├── pdf/
│   │   │   ├── reader.py    # PDF reading & text extraction
│   │   │   ├── renderer.py  # Page rendering
│   │   │   ├── text_detector.py    # Text block detection
│   │   │   ├── footer_detector.py  # Footer detection
│   │   │   ├── text_replacer.py    # Text replacement engine
│   │   │   └── exporter.py  # PDF export
│   │   └── models/
│   │       └── pdf_models.py # Data models
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── css/styles.css
│   └── js/app.js
├── uploads/          # Temporary upload storage
├── output/           # Exported PDFs
├── temp/             # Temporary files
├── run.py           # Application launcher
└── requirements.txt
```

## Supported PDF Types

### Fully Supported

- PDFs with real/selectable text
- PDFs with standard fonts
- Multi-page documents
- Password-protected PDFs (with password)

### Limited Support

- PDFs with embedded/custom fonts (closest font will be used)
- PDFs with unusual encodings

### Not Supported

- Scanned/image-only PDFs (text is not selectable)
- PDFs with DRM protection

## Privacy & Security

- **100% Local**: All processing happens on your computer
- **No Uploads**: PDFs never leave your machine
- **No Accounts**: No registration or login required
- **No Limits**: Process unlimited PDFs
- **Original Safe**: Your original PDF is never modified

## Troubleshooting

### Application won't start

Ensure all dependencies are installed:
```bash
pip install -r requirements.txt
```

### PDF won't open

- Check if the file is a valid PDF
- If password-protected, enter the password when prompted
- Try opening the PDF in another viewer to verify it's not corrupted

### Text not selectable

The PDF may contain image-based text (scanned). This editor works best with PDFs that have selectable text.

## License

MIT License - Free to use and modify.
