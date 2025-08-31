# metadata_parser.py

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Optional
import uuid

def parse_metadata(xml_path: Path) -> Dict[str, Optional[str]]:
    """
    Phân tích tệp metadata.xml để lấy các thông tin cần thiết cho EPUB.

    Args:
        xml_path: Đường dẫn đến tệp metadata.xml.

    Returns:
        Một dictionary chứa các thông tin metadata.
    """
    namespaces = {
        'dc': 'http://purl.org/dc/elements/1.1/',
        'opf': 'http://www.idpf.org/2007/opf'
    }

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        # Helper function to find text safely
        def find_text(query):
            element = root.find(query, namespaces)
            return element.text if element is not None else None

        # Lấy các thông tin cần thiết
        book_title = find_text('dc:title') or "Không có tiêu đề"
        book_lang = find_text('dc:language') or "vi"
        book_creator = find_text('dc:creator') or "Không rõ tác giả"
        
        # Tìm identifier, nếu không có thì tạo một UUID mới
        identifier_element = root.find("dc:identifier[@id='bookid']", namespaces)
        if identifier_element is not None:
            book_id = identifier_element.text
        else:
            book_id = 'urn:uuid:' + str(uuid.uuid4())
        
        book_date = find_text('dc:date')

        return {
            'title': book_title,
            'language': book_lang,
            'creator': book_creator,
            'identifier': book_id,
            'date': book_date
        }

    except (ET.ParseError, FileNotFoundError) as e:
        print(f"Lỗi khi xử lý metadata '{xml_path}': {e}")
        return {
            'title': "Lỗi tiêu đề",
            'language': "vi",
            'creator': "N/A",
            'identifier': 'urn:uuid:' + str(uuid.uuid4()),
            'date': None
        }