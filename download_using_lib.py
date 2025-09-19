import os
import re
import argparse
import tempfile
from PyPDF2 import PdfMerger
from pesuacademy import PESUAcademy
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def sanitize_filename(name):
    # Remove or replace characters not allowed in file/folder names across platforms

    # Replace problematic characters
    sanitized = re.sub(r'[\\/:*?"<>|\r\n\t]', "_", name)

    # Remove leading/trailing whitespace and dots
    sanitized = sanitized.strip(" .")

    # Ensure name is not empty and not a reserved name
    reserved_names = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        "COM1",
        "COM2",
        "COM3",
        "COM4",
        "COM5",
        "COM6",
        "COM7",
        "COM8",
        "COM9",
        "LPT1",
        "LPT2",
        "LPT3",
        "LPT4",
        "LPT5",
        "LPT6",
        "LPT7",
        "LPT8",
        "LPT9",
    }
    if sanitized.upper() in reserved_names or not sanitized:
        sanitized = f"file_{sanitized}" if sanitized else "unnamed"

    # Limit length to 255 characters (common filesystem limit)
    if len(sanitized) > 255:
        sanitized = sanitized[:252] + "..."

    return sanitized


async def download_file(session, url, dest):
    resp = await session.get(url)
    if resp.status_code == 200:
        with open(dest, "wb") as f:
            f.write(resp.content)
    else:
        print(f"Failed to download {url} (status {resp.status_code})")


async def main():
    parser = argparse.ArgumentParser(description="Download PESU Academy course materials.")
    parser.add_argument("--course", type=str, required=True, help="Course name (case sensitive)")
    parser.add_argument("--semester", type=int, required=True, help="Semester number")
    parser.add_argument(
        "--mode",
        type=str,
        choices=["folder", "singlepdf"],
        default="folder",
        help="Output mode: folder (hierarchical) or singlepdf (merge all PDFs)",
    )
    parser.add_argument(
        "--output", type=str, default=None, help="Output file/folder name (optional)"
    )
    parser.add_argument(
        "--filetype", type=int, default=2, help="Material type: 2 for slides, 3 for notes, etc."
    )
    args = parser.parse_args()

    # Get credentials from environment variables
    username = os.getenv("PESU_USERNAME")
    password = os.getenv("PESU_PASSWORD")

    if not username or not password:
        print("Error: PESU_USERNAME and PESU_PASSWORD must be set in .env file")
        return

    p = await PESUAcademy.login(username, password)
    courses = await p.get_courses(semester=args.semester)
    courses = list(courses.values())[0]
    try:
        dc = next(course for course in courses if course.title == args.course)
    except StopIteration:
        print(f"Course '{args.course}' not found in semester {args.semester}.")
        return

    output_name = args.output or sanitize_filename(dc.title)
    units = await p.get_units_for_course(dc.id)
    session = p._client._session

    if args.mode == "folder":
        os.makedirs(output_name, exist_ok=True)
        for unit in units:
            unit_folder = os.path.join(output_name, sanitize_filename(unit.title.strip()))
            os.makedirs(unit_folder, exist_ok=True)
            topics = await p.get_topics_for_unit(unit.id)
            for topic in topics:
                topic_folder = os.path.join(unit_folder, sanitize_filename(topic.title.strip()))
                os.makedirs(topic_folder, exist_ok=True)
                materials = await p.get_material_links(topic, args.filetype)
                for material in materials:
                    ext = os.path.splitext(material.url)[1] or ".pdf"
                    safe_title = sanitize_filename(material.title.strip())
                    filename = f"{safe_title}{ext}"
                    dest_path = os.path.join(topic_folder, filename)
                    print(f"Downloading: {material.title} -> {dest_path}")
                    await download_file(session, material.url, dest_path)
    else:  # singlepdf mode, but one merged PDF per unit
        os.makedirs(output_name, exist_ok=True)
        with tempfile.TemporaryDirectory() as tmpdir:
            for unit in units:
                unit_pdf_paths = []
                topics = await p.get_topics_for_unit(unit.id)
                for topic in topics:
                    materials = await p.get_material_links(topic, args.filetype)
                    for material in materials:
                        ext = os.path.splitext(material.url)[1] or ".pdf"
                        if ext.lower() != ".pdf":
                            continue  # Only merge PDFs
                        safe_title = sanitize_filename(material.title.strip())
                        filename = f"{safe_title}{ext}"
                        dest_path = os.path.join(tmpdir, filename)
                        print(f"Downloading: {material.title} -> {dest_path}")
                        await download_file(session, material.url, dest_path)
                        unit_pdf_paths.append(dest_path)
                if not unit_pdf_paths:
                    print(f"No PDF files found to merge for unit: {unit.title}")
                    continue
                merger = PdfMerger()
                for pdf in unit_pdf_paths:
                    merger.append(pdf)
                unit_pdf_name = sanitize_filename(unit.title.strip()) + ".pdf"
                merged_pdf = os.path.join(output_name, unit_pdf_name)
                merger.write(merged_pdf)
                merger.close()
                print(f"Merged PDF for unit saved as {merged_pdf}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
