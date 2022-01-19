import logging

from sortedcontainers import SortedSet

from tellus.sources import Source
from tellus.configuration import TELLUS_INTERNAL
from tellus.tell import Tell

from tellus.tells import DuplicateTellException


class ConfluenceSource(Source):
    """
    The general Source for pulling information from Confluence into Tellus.
    """

    SOURCE_ID = "confluence"

    def __init__(self, teller, confluence):
        super().__init__(
            teller,
            source_id=ConfluenceSource.SOURCE_ID,
            description="Pulls information from Confluence into Tellus.",
            datum_display_name="Confluence",
        )
        self._confluence = confluence
        self._pages_retrieved = 0
        self._confluence_tells = Source.create_transient_teller()  # an Experiment

    async def load_source(self):
        new_teller = Source.create_transient_teller()
        self._pages_retrieved = len(self.load_all_pages(new_teller))
        self._confluence_tells = (
            new_teller  # Note we are wholly swapping out the Teller each time
        )

    def load_all_pages(self, new_teller, space="AQ"):
        start_page = 0
        pages_to_retrieve = 200
        max_pages = 5000  # Just a guard rail
        more_pages = True
        page_names = SortedSet()

        while more_pages:
            pages = self._confluence.get_all_pages_from_space(
                space, start=start_page, limit=pages_to_retrieve
            )
            logging.debug("%s pages returned", len(pages))
            for page in pages:
                page_name = page.get("title")
                try:
                    page_tell = new_teller.create_tell(
                        page_name, TELLUS_INTERNAL, self.source_id
                    )
                except DuplicateTellException:
                    logging.info("A Tell already exists for ")

                page_data = {
                    Tell.DESCRIPTION: page_name,
                    Tell.GO_URL: page.get("_links").get("tinyui"),
                }
                page_tell.update_data_from_source(self.source_id, page_data)

                page_names.add(page_name)
            if len(pages) < pages_to_retrieve or start_page > max_pages:
                more_pages = False
            else:
                start_page += pages_to_retrieve

        return page_names

    @property
    def pages_retrieved(self):
        return self._pages_retrieved

    @property
    def page_tell_count(self):
        return self._confluence_tells.tells_count()

    @property
    def transient_teller(self):
        return self._confluence_tells
