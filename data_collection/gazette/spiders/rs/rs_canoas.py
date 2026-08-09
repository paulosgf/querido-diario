import datetime as dt

import scrapy
from scrapy.http import FormRequest

from gazette.items import Gazette
from gazette.spiders.base import BaseGazetteSpider
from gazette.utils.dates import daily_sequence

# GLOBALS URLS FOR ALL METHODS
old_url = "https://sistemas.canoas.rs.gov.br/gt/publico/dof/index.jsf"
new_url = "https://sistemas.canoas.rs.gov.br/domc/pesquisar?publication_date="
headers = {
    "Accept": "application/xml, text/xml, */*; q=0.01",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Faces-Request": "partial/ajax",
    "X-Requested-With": "XMLHttpRequest",
}


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
        # SELECT OLD OR NEW URL
        uri = response.url
        if old_url in uri:
            # OLD URL - STEP 1: HOME PAGE -> CLICK SEARCH
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
                "j_idt35:tipoPublicacao1_focus": "",
                "j_idt35:tipoPublicacao1_input": "Todos",
                "j_idt35:palavrasChave1": "",
                "javax.faces.ViewState": view_state,
            }

            # Creating a local copy of the headers to avoid asynchronous scope leakage
            req_headers = headers.copy()
            req_headers["Referer"] = uri

            yield FormRequest(
                url=uri,
                formdata=data,
                headers=req_headers,
                callback=self.parse_table_sections,
            )
        elif new_url in uri:
            # NEW URL - UNIQUE STEP
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

    def parse_table_sections(self, response):
        # OLD URL - STEP 2: -> CLICK ON THE SECTION TABLE ROW
        inner_html = response.xpath(
            '//update[contains(text(), "j_idt73")]/text()'
        ).get()
        if not inner_html:
            self.logger.error(
                "Não foi possível encontrar o componente da tabela na resposta."
            )
            return

        seletor = scrapy.Selector(text=inner_html)
        view_state = response.xpath(
            '//update[@id="javax.faces.ViewState"]/text()'
        ).get()
        primary_row_key = seletor.xpath("//tr[@data-rk]/@data-rk").get()

        if not primary_row_key:
            self.logger.error(
                "Nenhuma seção/linha foi encontrada na tabela para este dia."
            )
            return

        data_row_click = {
            "javax.faces.partial.ajax": "true",
            "javax.faces.source": "j_idt73:j_idt74",
            "javax.faces.partial.execute": "j_idt73:j_idt74",
            "javax.faces.partial.render": "colunaDireita",
            "javax.faces.behavior.event": "rowSelect",
            "javax.faces.partial.event": "rowSelect",
            "j_idt73:j_idt74_instantSelectedRowKey": primary_row_key,
            "j_idt73": "j_idt73",
            "j_idt73:j_idt74_selection": primary_row_key,
            "javax.faces.ViewState": view_state,
        }

        req_headers = headers.copy()
        req_headers["Referer"] = response.url

        yield FormRequest(
            url=response.url,
            formdata=data_row_click,
            headers=req_headers,
            callback=self.parse_transition_page,
            dont_filter=True,
        )

    def parse_transition_page(self, response):
        # OLD URL - STEP 3: -> CLICK ON THE UNIQUE FILE DOM BUTTON TO ARRIVE AT LAST PAGE
        view_state = response.xpath(
            '//update[@id="javax.faces.ViewState"]/text()'
        ).get()

        payload_download = {
            "javax.faces.partial.ajax": "true",
            "javax.faces.source": "j_idt90:j_idt98",
            "javax.faces.partial.execute": "@all",
            "javax.faces.partial.render": "colunaDireita",
            "j_idt90:j_idt98": "j_idt90:j_idt98",
            "j_idt90": "j_idt90",
            "j_idt90:publicacoes_focus": "",
            "j_idt90:publicacoes_input": "",
            "javax.faces.ViewState": view_state,
        }

        req_headers = headers.copy()
        req_headers["Referer"] = response.url

        yield FormRequest(
            url=response.url,
            formdata=payload_download,
            headers=req_headers,
            callback=self.parse_download_buttom,
            dont_filter=True,
        )

    def parse_download_buttom(self, response):
        # OLD URL - STEP 4: DIRECT URL EXTRACTION FOR THE GAZETTE (END OF FLOW)
        inner_html = response.xpath(
            '//update[contains(text(), "j_idt109")]/text()'
        ).get()

        if not inner_html:
            self.logger.error("Não foi possível extrair o HTML interno na tela final.")
            return

        seletor = scrapy.Selector(text=inner_html)

        # 1. Captures the relative link from within the <object> tag found in the XML.
        link_relativo = seletor.xpath('//object[@type="application/pdf"]/@data').get()

        if not link_relativo:
            self.logger.error("Link do PDF não encontrado dentro do objeto HTML.")
            return

        # 2. Converts the relative link into an absolute URL (automatically cleans up '&amp;')
        url_direta_pdf = response.urljoin(link_relativo)
        self.logger.info(
            f"URL direta enviada para a Pipeline do Gazette: {url_direta_pdf}"
        )

        # 3. Returns the final item expected by the Querido Diário framework.
        yield Gazette(
            date=self.start_date,
            file_urls=[url_direta_pdf],
            is_extra_edition=False,  # Ajuste se houver lógica para edições extra
            power="executive",
        )
