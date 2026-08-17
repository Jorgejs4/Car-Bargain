from scrapers.base.detail import extract_detail_text, extract_record_description


def test_extract_record_description_from_nested_payload() -> None:
    record = {"vehicle": {"sellerDescription": "Vehículo cuidado y revisado."}}

    assert extract_record_description(record) == "Vehículo cuidado y revisado."


def test_extract_detail_text_from_metadata_and_next_data() -> None:
    html = """
    <html><head>
      <meta property="og:title" content="BMW 320d" />
      <script id="__NEXT_DATA__" type="application/json">
        {"props":{"pageProps":{"listing":{"description":"Sin accidentes, garantía incluida."}}}}
      </script>
    </head></html>
    """

    result = extract_detail_text(html)
    assert result["title"] == "BMW 320d"
    assert result["description"] == "Sin accidentes, garantía incluida."
