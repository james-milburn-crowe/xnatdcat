"""Simple tool to query an XNAT instance and serialize projects as datasets"""
import logging

from rdflib import DCAT, DCTERMS, FOAF, Graph, Namespace, URIRef
from rdflib.term import Literal

from src.img2catalog.dcat_model import DCATCatalog, DCATDataSet, VCard
from typing import Dict, List


VCARD = Namespace("http://www.w3.org/2006/vcard/ns#")

logger = logging.getLogger(__name__)


class GCParserError(ValueError):
    """Exception that can contain an list of errors from the XNAT parser.

    Parameters
    ----------
    message: str
        Exception message
    error_list: list
        List of strings containing error messages.

    """

    def __init__(self, message: str, error_list: List[str]):
        super().__init__(message)
        self.error_list = error_list


def gc_to_DCATDataset(dataset: Dict) -> DCATDataSet:
    """This function populates a DCAT Dataset class from an GC project

    Currently fills in the title, description and keywords. The first two are mandatory fields
    for a dataset in DCAT-AP, the latter is a bonus.

    Note: Some fields are missing in grand challenge, we need the option to supply

    Parameters
    ----------
    response : Dict

    extraInfo : Dict
        A dictionary containing extra info not found in the GC download

    Returns
    -------
    DCATDataSet
        DCATDataSet object with fields filled in
    """
    error_list = []
    if not (dataset['creator']):
        error_list.append("Cannot have empty name of creator")
    if not dataset["description"]:
        error_list.append("Cannot have empty description")

    if error_list:
        raise GCParserError("Errors encountered during the parsing of GC Data.", error_list=error_list)

    creator_vcard = [
        VCard(
            full_name=Literal(dataset['creator']),
            uid=URIRef("http://example.com"),  # Should be ORCID?
        )
    ]

    project_dataset = DCATDataSet(
        uri=URIRef(dataset["url"]),
        title=[Literal(dataset["title"])],
        description=Literal(dataset["description"]),
        creator=creator_vcard,
        keyword=[Literal(dataset["keyword"])],  # Not implemented yet in gc, but we should look at making some
    )

    return project_dataset


def gc_to_DCATCatalog(response: Dict) -> DCATCatalog:
    """Creates a DCAT-AP compliant Catalog from Grand Challenge Data

    Parameters
    ----------
    response: The response from a grand challenge query
    Returns
    -------
    DCATCatalog
        DCATCatalog object with fields filled in
    """
    catalog_uri = URIRef(response['url'])
    catalog = DCATCatalog(
        uri=catalog_uri,
        title=Literal(response['title']),
        description=Literal(response['description']),
    )
    return catalog


def gc_to_RDF(data: Dict) -> Graph:
    """Creates a DCAT-AP compliant Catalog of Datasets from Grand Challenge

    Parameters
    ----------
        data: A dictionary of projects with metadata attached

    Returns
    -------
    Graph
        An RDF graph containing DCAT-AP
    """
    export_graph = Graph()

    # To make output cleaner, bind these prefixes to namespaces
    export_graph.bind("dcat", DCAT)
    export_graph.bind("dcterms", DCTERMS)
    export_graph.bind("foaf", FOAF)
    export_graph.bind("vcard", VCARD)

    catalog = gc_to_DCATCatalog(data["dataCatalog"])

    failure_counter = 0

    for p in data["dataSet"]:
        print(p)
        try:
            dcat_dataset = gc_to_DCATDataset(p)
            d = dcat_dataset.to_graph(userinfo_format=VCARD.VCard)
            catalog.Dataset.append(dcat_dataset.uri)
        except GCParserError as v:
            logger.info(f"Project {p.name} could not be converted into DCAT: {v}")
            for err in v.error_list:
                logger.info(f"- {err}")
            failure_counter += 1
            continue
        export_graph += d

    export_graph += catalog.to_graph()

    if failure_counter > 0:
        logger.warning("There were %d projects with invalid data for DCAT generation", failure_counter)

    return export_graph
