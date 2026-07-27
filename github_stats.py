import os
import requests
from lxml import etree

USERNAME = "Arish0limbu"
TOKEN = os.environ["ACCESS_TOKEN"]

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}

GRAPHQL_URL = "https://api.github.com/graphql"


def github_query(query, variables=None):
    response = requests.post(
        GRAPHQL_URL,
        json={
            "query": query,
            "variables": variables or {}
        },
        headers=HEADERS
    )

    response.raise_for_status()

    data = response.json()

    if "errors" in data:
        raise Exception(data["errors"])

    return data["data"]


def get_basic_stats():
    query = """
    query($login:String!){
      user(login:$login){

        repositories(
          first:100,
          ownerAffiliations:[OWNER]
        ){
          totalCount
          nodes{
            stargazerCount
          }
        }

        followers{
          totalCount
        }

        repositoriesContributedTo(
          contributionTypes:[COMMIT,ISSUE,PULL_REQUEST,REPOSITORY],
          includeUserRepositories:true
        ){
          totalCount
        }

      }
    }
    """

    user = github_query(
        query,
        {
            "login": USERNAME
        }
    )["user"]

    stars = sum(
        repo["stargazerCount"]
        for repo in user["repositories"]["nodes"]
    )

    return {
        "repos": user["repositories"]["totalCount"],
        "stars": stars,
        "followers": user["followers"]["totalCount"],
        "contributed": user["repositoriesContributedTo"]["totalCount"],
    }

<<<<<<< HEAD
if __name__=="__main__":
    update_svg("dark.svg")
    print("SVG updated for",USER_NAME)
=======

def replace(root, element_id, value):
    element = root.find(f".//*[@id='{element_id}']")

    if element is not None:
        element.text = str(value)
def make_dots(label_length, value):
    value = str(value)
    dots = 40 - label_length - len(value)

    if dots < 1:
        dots = 1

    return "." * dots


def update_svg(svg_file):
    stats = get_basic_stats()

    tree = etree.parse(svg_file)
    root = tree.getroot()

    replace(root, "repo_data", stats["repos"])
    replace(root, "star_data", stats["stars"])
    replace(root, "contrib_data", stats["contributed"])
    replace(root, "follower_data", stats["followers"])

    replace(root, "repo_data_dots",
            make_dots(len("Repositories"), stats["repos"]))

    replace(root, "star_data_dots",
            make_dots(len("Stars"), stats["stars"]))

    replace(root, "contrib_data_dots",
            make_dots(len("Contributed"), stats["contributed"]))

    replace(root, "follower_data_dots",
            make_dots(len("Followers"), stats["followers"]))

    tree.write(
        svg_file,
        encoding="utf-8",
        xml_declaration=True
    )


if __name__ == "__main__":
    SVG_FILE = "dark.svg"

    if not os.path.exists(SVG_FILE):
        raise FileNotFoundError(
            f"{SVG_FILE} not found."
        )

    print("Fetching GitHub statistics...")

    update_svg(SVG_FILE)

    print("Done!")
>>>>>>>
