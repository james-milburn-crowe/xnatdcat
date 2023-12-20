import gcapi
import os
import argparse
from datetime import date
import json
from src.gcdcat.gc_parser import gc_to_RDF

def __parse_args():
    parser = argparse.ArgumentParser()
    required = parser.add_argument_group('required arguments')
    required.add_argument(
        "-c",
        "--credentials",
        help="file containing your github access token"
    )
    required.add_argument("-a", "--archives", help="List of archives to read from", required=True)
    required.add_argument("-o", "--output", help="Output Folder", required=True)
    required.add_argument("-f", "--fields", required=True)
    required.add_argument("-r", "--repository", required=True)
    required.add_argument("-x", "--extra_data", help="Extra data file" required=True)
    return parser.parse_args()


def __get_client(credential_file):
    """Grand challenge has no session features, so we include the client so we can do some recursive API calls

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
            else:
                if extra_data[archive][field]:
                    image_record[field] = extra_data[archive][field]
        image_records.add(image_record)
    return image_records


def __get_data_for_archive(client, response, fields, extra_data):
    archive_data = {}
    for field in fields["dataSet"]:
        if response[field]:
            archive_data[field] = response[field]
        else:
            if extra_data[field]:
                archive_data[field] = extra_data[field]

    image_records = __get_data_from_images(client, response, fields, extra_data)
    archive_data["dataCatalogRecords"] = image_records
    return archive_data

def git_push(repo, commit_message):
    try:
        repo = Repo(repo)
        repo.git.add(update=True)
        repo.index.commit(commit_message)
        origin = repo.remote(name='origin')
        origin.push()
    except:
        print('Some error occurred while pushing the code')


def cli_main():
    args = __parse_args()
    client = __get_client(args.credentials)
    extra_data = __get_extra_data(args.extra_data)
    archive = client.archives.detail(slug=args.archive)
    data = __get_data_for_archive(client, archive, args.fields, extra_data)
    g = gc_to_RDF(data)
    outfile = os.path.join(args.output, date.today().strftime('%Y-%m-%d'))
    with open(outfile, "w") as file:
        outfile.write(g)
