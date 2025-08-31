# metadata_parser.py

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Optional
import uuid

def parse_metadata(xml_path: Path) -> Dict[str, Optional[str]]:
    """
    Phân tích tệp metadata.xml để lấy các thông tin cần thiết cho EPUB,
    bao gồm cả các thẻ meta tùy chỉnh cho Calibre.
    """
    # opf: namespace mặc định cho các thẻ meta trong content.opf
    namespaces = {
        'dc': 'http://purl.org/dc/elements/1.1/',
        'opf': 'http://www.idpf.org/2007/opf'
    }

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        def find_text(query):
            element = root.find(query, namespaces)
            return element.text if element is not None else None

        book_title = find_text('dc:title') or "Không có tiêu đề"
        book_lang = find_text('dc:language') or "vi"
        book_creator = find_text('dc:creator') or "Không rõ tác giả"
        
        identifier_element = root.find("dc:identifier[@id='bookid']", namespaces)
        book_id = identifier_element.text if identifier_element is not None else 'urn:uuid:' + str(uuid.uuid4())
        
        book_date = find_text('dc:date')
        
        # <<< THÊM TÍNH NĂNG MỚI TẠI ĐÂY >>>
        # Tìm các thẻ meta của Calibre bằng namespace opf.
        series_element = root.find("opf:meta[@name='calibre:series']", namespaces)
        series = series_element.get('content') if series_element is not None else None

        series_index_element = root.find("opf:meta[@name='calibre:series_index']", namespaces)
        series_index = series_index_element.get('content') if series_index_element is not None else None
        
        # Xây dựng dictionary kết quả
        result = {
            'title': book_title,
            'language': book_lang,
            'creator': book_creator,
            'identifier': book_id,
            'date': book_date
        }
        # Chỉ thêm các key của Calibre nếu chúng tồn tại
        if series:
            result['series'] = series
        if series_index:
            result['series_index'] = series_index
            
        return result

    except (ET.ParseError, FileNotFoundError) as e:
        print(f"Lỗi khi xử lý metadata '{xml_path}': {e}")
        return {
            'title': "Lỗi tiêu đề", 'language': "vi", 'creator': "N/A",
            'identifier': 'urn:uuid:' + str(uuid.uuid4()), 'date': None
        }