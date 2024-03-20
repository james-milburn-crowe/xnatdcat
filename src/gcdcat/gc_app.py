import gcapi
import os
from pathlib import Path
from datetime import date
import json
from src.gcdcat.gc_parser import gc_to_RDF
import click


def __get_client(credential_file):
    """Grand challenge has no session features, so we include the client, so we can do some recursive API calls

    The client needs a credential token, which is supplied from a file to avoid exposing it on the commandline

    """
    with open(credential_file) as f:
        token = f.read().strip()
        return gcapi.Client(token=token)


def __get_extra_data(extra_data_file):
    """
    Expects a Json file structured like:
    archive_name: {
        owner: x
        license: y
        images: {
            licence: x
        }
    }
    """
    with open(extra_data_file):
        data = json.loads(extra_data_file.read())
    return data


def __get_data_from_images(client, archive,  fields, extra_data):
    """extra_data_file is used to fill in some of the fields that do not occur in grand challenge"""
    response = client(
        url="https://grand-challenge.org/api/v1/cases/images/",
        params={'archive': archive['pk']}
    )
    images = response['results']
    image_records = []
    for image in images:
        image_record = {}
        for field in fields["dataCatalogRecords"]:
            if image[field]:
                image_record[field] = image[field]
            elif field in extra_data["dataCatalogRecord"]:
                image_record[field] = extra_data["dataCatalogRecord"][field]
            else:
                image_record[field] = ""
        image_records.append(image_record)
    return image_records


def __get_data_for_archive(client, response, fields, extra_data):
    archive_data = {}
    for field in fields["dataSet"]:
        if field in response:
            archive_data[field] = response[field]
        elif field in extra_data["dataSet"]:
            archive_data[field] = extra_data["dataSet"][field]
        else:
            archive_data[field] = ""
    image_records = __get_data_from_images(client, response, fields, extra_data)
    archive_data["dataCatalogRecords"] = image_records
    return archive_data

def __get_data_for_catalog(fields, extra_data):
    """
    Grand challenge does not have any wider catalog metadata,
    so it needs to come from extra data
    """
    catalog_data = {}
    for field in fields["dataCatalog"]:
        catalog_data[field] = extra_data["dataCatalog"][field]
    return catalog_data


@click.command('gcdcat')
@click.option(
    "-c"
    "--credentials",
    help="Provide a file containing credentials",
    type = click.Path(file_okay=True, dir_okay=False, path_type=Path, writable=True),
    required=True,
)
@click.option(
    "-a"
    "--archives",
    help="List of archives to read from"
)
@click.option(
    "--output",
    help="Output directory",
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path, writable=True),
)
@click.option(
    "-f"
    "--fields",
    help="fields required from grand challenge")
@click.option(
    "-d"
    "--extra_data",
    help="Location of a supplementary datafile for missing fields",
    default=None,
    type = click.Path(file_okay=True, dir_okay=False, path_type=Path, writable=True),
)
@click.option(
    "-f",
    "--format",
    default="turtle",
    type=click.Choice(
        ["xml", "n3", "turtle", "nt", "pretty-xml", "trix", "trig", "nquads", "json-ld", "hext"], case_sensitive=False
    ),
    help=(
        "The format that the output should be written in. This value references a"
        " Serializer plugin in RDFlib. Supportd values are: "
        ' "xml", "n3", "turtle", "nt", "pretty-xml", "trix", "trig", "nquads",'
        ' "json-ld" and "hext". Defaults to "turtle".'
    ),
)
@click.pass_context
def gc_run(ctx: click.Context, output: click.Path, credentials: click.Path):
    client = __get_client(credentials)
    extra_data_path = ctx.obj["extra_data"]
    archives = ctx.obj["archives"]
    fields = ctx.obj["fields"]
    extra_data = __get_extra_data(extra_data_path)
    data = {}
    archives_data = []
    for a in archives:
        archive_response = client.archives.detail(slug=a)
        archive_data = __get_data_for_archive(client, archive_response, fields, extra_data)
        archives_data.append(archive_data)
    data["dataCatalog"] = __get_data_for_catalog(fields, extra_data)
    data["dataSet"] = archive_data
    g = gc_to_RDF(data)
    outfile = os.path.join(output, date.today().strftime('%Y-%m-%d'))
    with open(outfile, "w") as file:
       file.write(g.serialize())

