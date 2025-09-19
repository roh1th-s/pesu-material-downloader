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
    """Download file and return the actual content type and suggested filename"""
    resp = await session.get(url)
    if resp.status_code == 200:
        with open(dest, "wb") as f:
            f.write(resp.content)
        return resp.headers
    else:
        print(f"Failed to download {url} (status {resp.status_code})")
        return None


def get_file_extension_from_headers(headers, url, default_ext=".pdf"):
    """Extract file extension from HTTP headers or URL"""
    # First, try to get extension from Content-Disposition header
    content_disposition = headers.get("Content-Disposition", "")
    if content_disposition:
        # Look for filename in Content-Disposition header
        filename_match = re.search(r"filename[*]?=([^;]+)", content_disposition)
        if filename_match:
            filename = filename_match.group(1).strip("'\"")
            ext = os.path.splitext(filename)[1]
            if ext:
                return ext.lower()

    # Try to get extension from URL
    url_ext = os.path.splitext(url)[1]
    if url_ext:
        return url_ext.lower()

    # Default fallback
    return default_ext


def get_unique_filename(filepath):
    """Generate a unique filename by adding a number suffix if the file already exists"""
    if not os.path.exists(filepath):
        return filepath
    
    directory = os.path.dirname(filepath)
    filename_with_ext = os.path.basename(filepath)
    filename, extension = os.path.splitext(filename_with_ext)
    
    counter = 2
    while True:
        new_filename = f"{filename}_{counter}{extension}"
        new_filepath = os.path.join(directory, new_filename)
        if not os.path.exists(new_filepath):
            print(f"File already exists, renamed to: {new_filename}")
            return new_filepath
        counter += 1


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
        course = next(course for course in courses if course.title == args.course)
    except StopIteration:
        print(f"Course '{args.course}' not found in semester {args.semester}.")
        return

    output_name = args.output or sanitize_filename(course.title)
    units = await p.get_units_for_course(course.id)
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
                    safe_title = sanitize_filename(material.title.strip())

                    # Download to temporary location first to check headers
                    temp_filename = f"temp_{safe_title}"
                    temp_path = os.path.join(topic_folder, temp_filename)

                    print(f"Downloading: {material.title}...")
                    headers = await download_file(session, material.url, temp_path)

                    if headers is None:
                        continue  # Download failed

                    # Determine actual file extension from headers
                    actual_ext = get_file_extension_from_headers(headers, material.url)

                    # Handle different file types
                    if actual_ext.lower() == ".ppt":
                        # Save PPT as PPTX for consistency
                        final_ext = ".pptx"
                    else:
                        final_ext = actual_ext

                    # Rename file to final name with correct extension
                    final_filename = f"{safe_title}{final_ext}"
                    final_path = os.path.join(topic_folder, final_filename)
                    
                    # Handle duplicate filenames
                    unique_final_path = get_unique_filename(final_path)
                    try:
                        os.rename(temp_path, unique_final_path)
                        print(f"Saved as: {unique_final_path}")
                    except Exception as e:
                        print(f"Error saving file: {e}")
                        # Clean up temp file if rename failed
                        if os.path.exists(temp_path):
                            os.remove(temp_path)
    else:  # singlepdf mode, but one merged PDF per unit
        os.makedirs(output_name, exist_ok=True)
        with tempfile.TemporaryDirectory() as tmpdir:
            for unit in units:
                unit_pdf_paths = []
                topics = await p.get_topics_for_unit(unit.id)
                for topic in topics:
                    materials = await p.get_material_links(topic, args.filetype)
                    for material in materials:
                        safe_title = sanitize_filename(material.title.strip())

                        # Download to temporary location first to check headers
                        temp_filename = f"temp_{safe_title}"
                        temp_path = os.path.join(tmpdir, temp_filename)

                        print(f"Downloading: {material.title}...")
                        headers = await download_file(session, material.url, temp_path)

                        if headers is None:
                            continue  # Download failed

                        # Determine actual file extension from headers
                        actual_ext = get_file_extension_from_headers(headers, material.url)

                        # Rename to proper filename with extension
                        actual_filename = f"{safe_title}{actual_ext}"
                        actual_path = os.path.join(tmpdir, actual_filename)
                        
                        # Handle duplicate filenames
                        unique_actual_path = get_unique_filename(actual_path)
                        try:
                            os.rename(temp_path, unique_actual_path)
                            actual_path = unique_actual_path  # Update path for further processing
                            actual_filename = os.path.basename(actual_path)  # Update filename
                        except Exception as e:
                            print(f"Error renaming file: {e}")
                            # Clean up and skip this file
                            if os.path.exists(temp_path):
                                os.remove(temp_path)
                            continue

                        print(f"Detected file type: {actual_ext}")

                        # Handle different file types for PDF merging
                        if actual_ext.lower() in [".pptx", ".ppt"]:
                            print(f"Skipping {actual_filename} - PPTX/PPT files are not merged (use folder mode to keep them)")
                            os.remove(actual_path)
                        elif actual_ext.lower() == ".pdf":
                            unit_pdf_paths.append(actual_path)
                        else:
                            print(f"Skipping {actual_filename} - unsupported file type for PDF merging")
                            os.remove(actual_path)
                if not unit_pdf_paths:
                    print(f"No PDF files found to merge for unit: {unit.title}")
                    continue

                merger = PdfMerger()
                successful_merges = 0

                for pdf in unit_pdf_paths:
                    try:
                        merger.append(pdf)
                        successful_merges += 1
                    except Exception as e:
                        print(f"Warning: Could not merge {pdf}: {e}")
                        continue

                if successful_merges == 0:
                    print(f"No PDFs could be merged for unit: {unit.title}")
                    merger.close()
                    continue

                unit_pdf_name = sanitize_filename(unit.title.strip()) + ".pdf"
                merged_pdf = os.path.join(output_name, unit_pdf_name)
                merger.write(merged_pdf)
                merger.close()
                print(
                    f"Merged PDF for unit saved as {merged_pdf} ({successful_merges} files merged)"
                )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
