BLACKLIST = set()

import os,json
from  jsonpath import jsonpath
import yaml
import ruamel.yaml
from azure.devops.v6_0 import pipelines


from azure.devops.connection import Connection
from msrest.authentication import BasicAuthentication
import requests 
import base64

import logging

logger = logging.getLogger('change pipeline yaml')
logger.setLevel(logging.DEBUG)
# create file handler which logs even debug messages
fh = logging.FileHandler('yaml.log')
fh.setLevel(logging.DEBUG)
logger.addHandler(fh)


os.chdir(os.path.dirname(os.path.realpath(__file__)))

def loadfile(file):
    with open(file) as stream:
        try:
            yml=[yml for yml in yaml.safe_load_all(stream.read())]
            return yml
        except yaml.YAMLError as exc:
            print(exc)
            return 1


conf = loadfile("config.yaml")
token =  conf[0]["token"]
Azure_url = "https://fastalelo.visualstudio.com"
projectName=conf[0]['projectName']
Credentials = BasicAuthentication("", token)
connection = Connection(base_url=Azure_url, creds=Credentials)




def save_file(file_pipeline,code):

    # file = open(file_pipeline,"w") 
    with open(file_pipeline, "w") as f:

        ruamel.yaml.dump(
            code[0], f, Dumper=ruamel.yaml.RoundTripDumper,
            default_flow_style=False, width=50, indent=8)

    # ruamel.yaml.dump(code[0],file, Dumper= ruamel.yaml.RoundTripDumper)

    # yaml.safe_dump(code[0],file, sort_keys=False,default_flow_style=False) 


def post_url(pipeline_id,branch_name):

    url = 'https://fastalelo.visualstudio.com/6b5a6b54-fa73-4ac4-bb97-0e7f626e54e2/_apis/pipelines/'+ str(pipeline_id) +'/runs?api-version=6.0-preview.1'
    myobj = yaml.safe_load('{"stagesToSkip":[],"resources":{"repositories":{"self":{"refName":"refs/heads/' + branch_name + '"}}},"variables":{"system.debug":{"value":"false"}}}')

    authorization = str(base64.b64encode(bytes(':'+token, 'ascii')), 'ascii')

    headers = {
        'Accept': 'application/json',
        'Authorization': 'Basic '+authorization,
    }

    response = requests.post(url=url, headers=headers, json = myobj)
        
    return(response.status_code)


def request(url):
    authorization = str(base64.b64encode(bytes(':'+token, 'ascii')), 'ascii')

    headers = {
        'Accept': 'application/json',
        'Authorization': 'Basic '+authorization
    }

    response = requests.get(url=url, headers=headers)
        
    return(response.text)
    
def get_repo(repo_id):
    
    git_list = get_git_client()
    repos = git_list.get_repositories()
    
    for repo in repos:
        if repo.id == repo_id:
            return repo.remote_url


def get_git_client():
        git_client = connection.clients_v6_0.get_git_client()
        return git_client

def get_repositorie_client():
    release_client = connection.clients_v6_0.get_release_client()
    return release_client
    

def get_release_client():
    release_client = connection.clients_v6_0.get_release_client()
    return release_client
    
def get_build_client():
    build_client = connection.clients_v6_0.get_build_client()
    return build_client

def get_pipeline_client():
    pipeline_client = connection.clients_v6_0.get_pipelines_client()
    return pipeline_client

def get_build(id):
    build_client = get_build_client()
    return build_client.get_definition(projectName,id)


def get_policy_configuration(id):
    policies_client= get_policies_client()
    get_policy_configuration = policies_client.get_policy_configurations(projectName,id)

    return get_policy_configuration

def get_policy_configurations(policy_name):
    policies_client= get_policies_client()
    policy_id = get_policy_type(policy_name)
    policy_configurations = policies_client.get_policy_configurations(projectName,policy_type=policy_id)
    return policy_configurations

def get_policy_type(policy_name): 
    policies_list= get_policies_client()
    for policy in policies_list.get_policy_types(projectName):
        if policy_name == policy.display_name:                
                return policy.id

def get_policies_client():
        policies_client= connection.clients_v6_0.get_policy_client()
        return policies_client

  
def create_resource_policy(policies,repo_id,branch, requiredReviewerIds,list_policies):

        all_policies = []
        requiredReviewersPolicy = """{
            type: {
                id: %s
            },
            isEnabled: true,
            isBlocking: true,
            isDeleted: false,
            settings: {
                requiredReviewerIds: [
                    %s
                    ],
                    minimumApproverCount: 1,
                    creatorVoteCounts: true,
                "scope": [
                    {
                        "refName": "refs/heads/%s",
                        "matchKind": "Exact",
                        "repositoryId": %s
                    }
                ],
                "filenamePatterns": [
                    "/*"
                ]
            }
        }
        """ % (policies['Required reviewers'],requiredReviewerIds,branch,repo_id)

        all_policies.append(yaml.safe_load(requiredReviewersPolicy))

        minNumReviewersPolicy= """{
            type: {
                id: %s
            },
            isEnabled: true,
            isBlocking: true,
            isDeleted: false,
            settings: {
                "minimumApproverCount": 1,
                "creatorVoteCounts": true,
                "allowDownvotes": false,
                "resetOnSourcePush": false,
                "scope": [
                    {
                        "refName": "refs/heads/%s",
                        "matchKind": "Exact",
                        "repositoryId": %s
                    }
                ]
            }
        }""" % (policies['Minimum number of reviewers'],branch,repo_id)

        all_policies.append(yaml.safe_load(minNumReviewersPolicy))

        workItemLinkingPolicy ="""{
            type: {
                id: %s
            },
            isEnabled: true,
            isBlocking: true,
            isDeleted: false,
            settings: {
                "scope": [
                    {
                        "refName": "refs/heads/%s",
                        "matchKind": "Exact",
                        "repositoryId": %s
                    }
                ]
            }
        }""" % (policies['Work item linking'],branch,repo_id)
        if  "master" == branch :
                all_policies.append(yaml.safe_load(workItemLinkingPolicy))

        return all_policies


def delete_resource_policy(repo_id,branch):

    policies_client = get_policies_client()
    policies= ["Required reviewers","Minimum number of reviewers","Work item linking"]
    for policy_name in policies:
        policy_configurations = get_policy_configurations(policy_name)
        for configuration in policy_configurations:
                if configuration.settings['scope'][0]['repositoryId'] == repo_id and configuration.settings['scope'][0]['refName'] == 'refs/heads/' + branch:                         
                    # print(configuration)
                    try:
                        policies_client.delete_policy_configuration(projectName,configuration.id)
                    except:
                        pass

def delete_policies(repo_name,branch):
    
    git_list = get_git_client()
    repos = git_list.get_repositories()
    
    for repo in repos:
        if repo_name.strip() ==  repo.name:
                    delete_resource_policy(repo.id,branch)
    return "Delete Policy Sucess"


def create_policies(repo_name,branch):

    git_list = get_git_client()
    repos = git_list.get_repositories()

    for repo in repos:
        if repo_name.strip() ==  repo.name:
            repo_id = repo.id
            break

    policies_client = get_policies_client()

    policies_names= ["Required reviewers","Minimum number of reviewers","Work item linking"]
    
    policies = {}

    for policy_name in policies_names:
        policies["Required reviewers"] = get_policy_type("Required reviewers")
        policies[policy_name]= get_policy_type(policy_name)
    
    list_polices=  {'master':['requiredReviewersPolicy','minNumReviewersPolicy','workItemLinkingPolicy'],
                    'development': ['requiredReviewersPolicy']}
    ReviewerIds= {'master': 'a8a50913-2e70-46d1-866c-52dc478bb934','development':'91565209-9233-4e74-91c0-d46acdfee058'}

    policy_configurations = create_resource_policy(policies,repo_id,branch,ReviewerIds[branch],list_polices[branch])
    for configuration in policy_configurations:
        try:
            policies_client.create_policy_configuration(configuration,projectName)
        except Exception as e:
            print("error " + str(e))
            logging.debug(str(repo_name) + " " + str(e))
            pass


        # os.system("rm -rf " + src + '/' + scm_name)


def run_pipeline(list,branch,type_pipeline):

    pipeline_client = get_pipeline_client()
    pipeline_list = pipeline_client.list_pipelines(projectName,top=1000)
    for x in pipeline_list:
        for name in list:
            if   x.name == name:
                r= request(x.url)  
                type_conf = 'designerJson' if 'designerJson' in jsonpath(json.loads(r), '$..type') else  'yaml'
                if  type_conf == type_pipeline:              
                    try:
                        post_url(x.id,branch)
                    except Exception as e:
                        print(str(x.name) + " " + str(e) )


