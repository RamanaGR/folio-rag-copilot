from fpdf import FPDF


def build_cover_letter_pdf(text: str) -> bytes:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    for paragraph in text.split("\n"):
        pdf.multi_cell(0, 7, paragraph)
        pdf.ln(3)
    return bytes(pdf.output())
