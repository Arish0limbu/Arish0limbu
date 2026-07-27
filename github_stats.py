import os
import requests
from lxml import etree

HEADERS = {"authorization": "token " + os.environ["ACCESS_TOKEN"]}
USER_NAME = "Arish0limbu"

def graphql(query, variables):
    r = requests.post(
        "https://api.github.com/graphql",
        json={"query": query, "variables": variables},
        headers=HEADERS,
    )
    r.raise_for_status()
    return r.json()["data"]["user"]

def repos():
    q="""
    query($login:String!){
      user(login:$login){
        repositories(first:100,ownerAffiliations:[OWNER]){
          totalCount
          edges{node{stargazers{totalCount}}}
        }
      }
    }"""
    u=graphql(q,{"login":USER_NAME})
    stars=sum(e["node"]["stargazers"]["totalCount"] for e in u["repositories"]["edges"])
    return u["repositories"]["totalCount"],stars

def contributed():
    q="""
    query($login:String!){
      user(login:$login){
        repositories(ownerAffiliations:[OWNER,COLLABORATOR,ORGANIZATION_MEMBER]){
          totalCount
        }
      }
    }"""
    return graphql(q,{"login":USER_NAME})["repositories"]["totalCount"]

def followers():
    q="""
    query($login:String!){
      user(login:$login){followers{totalCount}}
    }"""
    return graphql(q,{"login":USER_NAME})["followers"]["totalCount"]

def replace(root,id_,text):
    e=root.find(f".//*[@id='{id_}']")
    if e is not None:
        e.text=str(text)

def update_svg(svg):
    repo,star=repos()
    contrib=contributed()
    follow=followers()
    tree=etree.parse(svg)
    root=tree.getroot()
    replace(root,"repo_data",repo)
    replace(root,"star_data",star)
    replace(root,"contrib_data",contrib)
    replace(root,"follower_data",follow)
    tree.write(svg,encoding="utf-8",xml_declaration=True)

if __name__=="__main__":
    update_svg("dark.svg")
    print("SVG updated for",USER_NAME)
