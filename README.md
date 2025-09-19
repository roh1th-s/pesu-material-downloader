# PESU Material Downloader

A Python script to download course materials (notes, slides, etc.) from PES University's PESU Academy portal.

## Installation

1. Clone this repository:

```bash
git clone https://github.com/roh1th-s/pesu-material-downloader.git
cd pesu-material-downloader
```

2. Create a virtual environment (recommended):

```bash
python -m venv .venv
.venv\Scripts\activate  # On Windows
# or
# source .venv/bin/activate  # On Linux/Mac
```

3. Install required dependencies:

```bash
pip install -r requirements.txt
```

## Usage

### Configuration

**Set up your credentials using environment variables:**

1. Copy the example environment file:

```bash
# On Windows
copy .env.example .env

# On Linux/Mac
cp .env.example .env
```

2. Edit the `.env` file with your PESU Academy credentials:

```env
PESU_USERNAME=your_pesu_username
PESU_PASSWORD=your_pesu_password
```

**Note**: The `.env` file is already added to `.gitignore` to keep your credentials secure and prevent them from being committed to version control.

### Basic Usage

```bash
python download_material.py --course "Course Name" --semester 5
```

### Command Line Arguments

-   `--course` (required): Course name (case sensitive)
-   `--semester` (required): Semester number
-   `--mode` (optional): Output mode
    -   `folder` (default): Hierarchical folder structure
    -   `singlepdf`: Merge PDFs into one file per unit
-   `--output` (optional): Custom output folder/file name
-   `--filetype` (optional): Material type (default: 2)
    -   `2`: Slides
    -   `3`: Notes
    -   Other values for different material types

### Examples

1. **Download slides in folder structure:**

```bash
python download_material.py --course "Digital Communication" --semester 5
```

2. **Download notes and merge into PDFs:**

```bash
python download_material.py --course "Digital Communication" --semester 5 --mode singlepdf --filetype 3
```

3. **Download with custom output name:**

```bash
python download_material.py --course "Digital Communication" --semester 5 --output "DigitalCom"
```

## Output Structure

### Folder Mode

```
Course Name/
├── Unit 1/
│   ├── Topic 1/
│   │   ├── material1.pdf
│   │   ├── presentation1.pptx
│   │   └── material2.pdf
│   └── Topic 2/
│       ├── material3.pdf
│       └── slides.pptx
└── Unit 2/
    └── Topic 3/
        └── material4.pdf
```

### Single PDF Mode

```
Course Name/
├── Unit_1.pdf
├── Unit_2.pdf
└── Unit_3.pdf
```

## Dependencies

-   [`pesuacademy`](https://github.com/pesu-dev/pesuacademy): Python library for PESU Academy API
-   [`PyPDF2`](https://pypi.org/project/PyPDF2/): PDF manipulation library for merging PDFs
-   [`python-dotenv`](https://pypi.org/project/python-dotenv/): For loading environment variables from .env file

## License

MIT
