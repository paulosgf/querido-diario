import datetime as dt

import scrapy
from scrapy.http import FormRequest

from gazette.items import Gazette
from gazette.spiders.base import BaseGazetteSpider
from gazette.utils.dates import daily_sequence

# GLOBALS URLS FOR ALL METHODS
old_url = "https://sistemas.canoas.rs.gov.br/gt/publico/dof/index.jsf"
new_url = "https://sistemas.canoas.rs.gov.br/domc/pesquisar?publication_date="


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
                yield scrapy.Request(url=old_url, callback=self.parse)
            elif day >= dt.date(2018, 5, 30):
                url = (
                    new_url
                    + self.start_date.strftime("%d/%m/%Y")
                    + "&publication_final_date="
                    + self.end_date.strftime("%d/%m/%Y")
                )
                yield scrapy.Request(url=url)

    def parse(self, response):
        uri = response.url
        if old_url in uri:
            view_state = response.css(
                'input[name="javax.faces.ViewState"]::attr(value)'
            ).get()
            data = {
                "javax.faces.partial.ajax": "true",
                "javax.faces.source": "j_idt35:j_idt50",
                "javax.faces.partial.execute": "@all",
                "javax.faces.partial.render": "j_idt35 colunaDireita growl",
                "j_idt35:j_idt50": "j_idt35:j_idt50",
                "j_idt35": "j_idt35",
                "j_idt35:dataPublicacao1_input": self.start_date.strftime("%d/%m/%Y"),
                "j_idt35%3AtipoPublicacao1_focus": "",
                "j_idt35:tipoPublicacao1_input": "Todos",
                "j_idt35:palavrasChave1": "",
                "javax.faces.ViewState": view_state,
                "Referer": uri,
            }
            headers = {
                "Accept": "application/xml, text/xml, */*; q=0.01",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Faces-Request": "partial/ajax",
                "X-Requested-With": "XMLHttpRequest",
            }
            post_request = FormRequest(
                url=uri, formdata=data, headers=headers, callback=self.parse_post_result
            )
            yield post_request
        elif new_url in uri:
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

    def parse_post_result(self, response):
        # O código vai pausar exatamente AQUI quando a resposta do POST chegar do servidor

        self.logger.info("Resposta do POST recebida com sucesso!")
        # Aqui você verá o XML do PrimeFaces contendo as tags <partial-response> e os novos dados
        print(response.text[:1000])
