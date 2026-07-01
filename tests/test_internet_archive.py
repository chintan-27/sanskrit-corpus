from sanskrit_corpus.internet_archive import select_files


def test_select_files_for_ocr_text() -> None:
    files = [{"name": "book_djvu.txt"}, {"name": "book.pdf"}, {"name": "meta.xml"}]

    assert select_files(files, "ocr_text") == [{"name": "book_djvu.txt"}]


def test_select_files_for_all() -> None:
    files = [{"name": "book_djvu.txt"}, {"name": "book.pdf"}, {"name": "book.epub"}, {"name": "meta.xml"}]

    assert len(select_files(files, "all")) == 3
