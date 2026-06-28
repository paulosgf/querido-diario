import datetime as dt

import scrapy

from gazette.items import Gazette
from gazette.spiders.base import BaseGazetteSpider
from gazette.utils.dates import daily_sequence


class UFMunicipioSpider(BaseGazetteSpider):
    name = "rs_canoas"
    TERRITORY_ID = "4304606"
    allowed_domains = ["sistemas.canoas.rs.gov.br"]
    start_urls = ["https://sistemas.canoas.rs.gov.br/domc/pesquisar?"]
    start_date = dt.date(2012, 11, 5)

    def start_requests(self):
        for d in daily_sequence(self.start_date, self.end_date, "%Y-%m-%d"):
            day = dt.datetime.strptime(d, "%Y-%m-%d").date()
            if day >= self.start_date and day <= dt.date(2018, 5, 29):
                url = "https://sistemas.canoas.rs.gov.br/gt/javax.faces.resource/dynamiccontent.properties.jsf?"
            elif day >= dt.date(2018, 5, 30):
                url = (
                    "https://sistemas.canoas.rs.gov.br/domc/pesquisar?publication_date="
                    + self.start_date.strftime("%d/%m/%Y")
                    + "&publication_final_date="
                    + self.end_date.strftime("%d/%m/%Y")
                )
        yield scrapy.Request(url=url)

    def parse(self, response):
        fileshare = "https://sistemas.canoas.rs.gov.br/domc/api/edition-file/"
        date_pattern = "([0-9]{2}/[0-9]{2}/[0-9]{4})"
        edition_pattern = r"Edição.*\b(\d+)"
        download_pattern = r"setPage\((\d+)"
        extra = False
        editions = response.css(".table-bordered")
        for edition in editions.xpath("//tbody/tr"):
            publication_date = edition.re(date_pattern, edition)
            publication_date = dt.datetime.strptime(
                "".join(publication_date), "%d/%m/%Y"
            ).date()
            edition_number = edition.re(edition_pattern, edition)
            edition_number = "".join(edition_number)
            if edition.re("Complementar", edition):
                extra = True
            download = edition.re_first(download_pattern)
            file_url = fileshare + download
        yield Gazette(
            date=publication_date,
            edition_number=edition_number,
            is_extra_edition=extra,
            file_urls=[file_url],
            power="executive",
        )
