"""New Enclave API

TODO's
  Want to replace enclave_api.py with this when done
  TO-DO: validate first, then change to do actual post
  TO-DO: find out whats required by doing a validate post
    - There should be API examples in response.json i got for this
    - Probably don't need the random ID we were using for new concept set / version
    - 1 & 2 are the most important.
    - Curl first and command at top of function for easy testing
    - For unit test, use validate url?
  0. Test case file. Might want to write a unit test for this.
    - test_enclave.py. 3 palantir files; just a single concept set.
  1. Create a new concept set
    1.1. Create a new concept set (see: createNewConceptSetDescription; "apiName": "create-new-concept-set",)
    1.2. Create new draft (see: createNewDraft; "apiName": "create-new-draft-omop-concept-set-version",)
      - This will be empty at first; the first draft.
    1.3. Add concepts to the draft.
    1.4. Approve: Turn draft into a version.
    Once first is working, should be able to figure out the second.
  2. Add/remove concepts from existing concept set
    - (Siggie doesn't know the steps)
  3. Change metadata on existing concept set
    - (Siggie doesn't know the steps)

todo's (later/minor/contingent)
  - to-do: contingent: @amin/enclave: Concept set ownership. Right now, personal access token is required. Service token
  (i.e. for bulk import) not allowed. This may create an issue later where, when a user is using TermHub and they upload
  a concept set, we will have to (a) use one of our personal access tokens, in which case it will not show in the
  enclave who really uploaded the concept set; it'll say one of us, or (b) we have the user pass their own personal
  access token. Amin (2022/10/19) said: "decision: onBehalfOf". I suppose this means that we'll add this optional param
  instead of an optional 'owner' param.
  - to-do: would we indeed represent OntologyObject types as Dict?

Notes
- Can't delete a concept-set-container. This is to prevent an accident where we delete something that someone else
depends on. This may change in the future; Amin could allow us to delete a specific concept set with a known name.
However, archive-concept-set is good enough for now.
    {
      "apiName": "",
      "description": "Sets Concept Set 'archived' property to true so that it no longer appears in browser",
      "rid": "ri.actions.main.action-type.cbc3643b-cca4-4772-ae2d-ae7036a6798b",
      "parameters": {
        "concept-set": {
          "description": "",
          "baseType": "OntologyObject"
        }
      }
    },

TODO: Remove this temporary list of API endpoints when done / if advisable
"""
import sys
from typing import Dict, List, Union

import requests

from enclave_wrangler.config import config, ENCLAVE_PROJECT_NAME


JSON_TYPE = Union[List, Dict]
VALIDATE_FIRST = True  # if True, will /validate before doing /apply, and return validation error if any.


# TODO: current implementation assumes all params same for each concept, but function needs to be completed
#  so that it checks for any differences and properly reroutes
# TODO: look futher down at add_concept_via_set(): Needs to be changed out
def add_concepts_to_cset(omop_concepts: List[Dict], version__codeset_id: int) -> JSON_TYPE:
    """Wrapper function for routing to appropriate endpoint. Add existing OMOP concepts to a versioned concept set / codeset.

    :param omop_concepts (List[Dict]): A list of dictionaries. Each dictionary must have a 'concept_id' (int) key
    which should be a valid OMOP concept ID. For additional params, refer to the documentation for the
    endpoint: set-omop-concept-set-version-item
    """
    # TODO: Calc if params are same
    params_same = True
    pass

    if params_same:
        response: JSON_TYPE = add_concepts_via_array(
            concepts=[x['concept_id'] for x in omop_concepts],
            version=version__codeset_id)  # == code_sets.codeset_id
    else:
        response: JSON_TYPE = []
        # TODO: This doesn't actually use correct endpoint, becuase can't pass codeset_id / concept set version ID.
        #  use this instead: add_concept_via_edit
        for concept in omop_concepts:
            response_i: JSON_TYPE = add_concept_via_set(  # concept_set_version_items / expressions
                include_descendants=concept['includeDescendants'],
                concept_set_version_item=concept['concept_id'],
                is_excluded=concept['isExcluded'],
                include_mapped=concept['includeMapped'])
            response.append(response_i)
    return response


# api_name = 'add-selected-concepts-as-omop-version-expressions'
def add_concepts_via_array(
    concepts: List[int], version: int, include_mapped=False, include_descendants=False, is_excluded=False,
    optional_annotation: str = None, validate_first=VALIDATE_FIRST
) -> JSON_TYPE:
    """Create new concepts within concept set, AKA concept_set_version_items / expressions
    Non-required params set to `None`.

    :param version (int): Same as code_sets.codeset_id. When uploaded, can view here:
    - https://unite.nih.gov/workspace/data-integration/dataset/preview/ri.foundry.main.dataset.7104f18e-b37c-419b-9755-a732bfa33b03/master
    - https://unite.nih.gov/workspace/module/view/latest/ri.workshop.main.module.5a6c64c0-e82b-4cf8-ba5b-645cd77a1dbf
    """
    api_name = 'add-selected-concepts-as-omop-version-expressions'
    # Commented out portions are part of the api definition
    d = {
        # "apiName": "add-selected-concepts-as-omop-version-expressions",
        # "description": "",
        # "rid": "ri.actions.main.action-type.d1ad39f8-a303-4f46-8f46-bd48c5362915",
        "parameters": {
            "concepts": concepts,
              # "description": "",
              # "baseType": "Array<OntologyObject>"
            "includeMapped": include_mapped,
              # "description": "If true, then these expression items will match on the selected OMOP Concepts, and all of the Non-Standard OMOP Concepts that map to them. If Include Descendants is also true, then this option will also include all OMOP Concepts that map to the included descendants. Setting this to true enables you to include non-standard Concepts in your Concept Set. Mapping is the process to transform one Concept into a Standard one. Read more: ohdsi.github.io/TheBookOfOhdsi/Cohorts.html#conceptSets and https://www.ohdsi.org/web/wiki/doku.php?id=documentation:vocabulary:mapping",
              # "baseType": "Boolean"
            "includeDescendants": include_descendants,
              # "description": "If true, then these expression items will match on the selected OMOP Concepts, and all of their descendants.",
              # "baseType": "Boolean"
            # version: More docs in function docstring.
            "version": version,
              # "description": "",
              # "baseType": "OntologyObject"
            "isExcluded": is_excluded,
              # "description": "If true, then any concepts matched will be added to the expression as exclusion rather than inclusion criteria. Exclusion criteria take precedence over inclusion criteria, in cases when a single OMOP Concept is affected by more than one entry in the OMOP Concept Set Expression.",
              # "baseType": "Boolean"
            "optional-annotation": optional_annotation,
              # "description": "What are you trying to accomplish? Reason?",
              # "baseType": "String"
        }
    }
    return post(api_name, d, validate_first)


# api_name = 'set-omop-concept-set-version-item'
# TODO: remove this, as can't pass the codeset_id / verion_id
# By default, we use `upload_concept_via_array`. However, `upload_concept_via_set` is likely more useful when the
# values of these params are not the same for every concept in the concept set.
def add_concept_via_set(
    include_descendants: bool, concept_set_version_item: str, is_excluded: bool, include_mapped: bool, validate_first=VALIDATE_FIRST
) -> JSON_TYPE:
    """Create new concepets within concept set
    Non-required params set to `None`.

    :param concept_set_version_item (str): todo: What to put here? OMOP concept_id? (item_id is a random uuid)

    Example curl:
        curl -H "Content-type: application/json" -H "Authorization: Bearer $OTHER_TOKEN" \
        https://unite.nih.gov/api/v1/ontologies/ri.ontology.main.ontology.00000000-0000-0000-0000-000000000000/actions/set-omop-concept-set-version-item/validate \
        --data '{"parameters":{"include_descendants":false }}' | jq
        - Validate: Use above CURL
        - Apply: (replace /validate with /apply in above string)
        - This is a sign that it worked: "curl: (52) Empty reply from server"

    Example validation:
    {
      "result": "INVALID",
      "submissionCriteria": [
        {
          "result": "INVALID",
          "configuredFailureMessage": "Condition not met"
        }
      ],
      "parameters": {
        "include_descendants": {
          "result": "VALID",
          "evaluatedConstraints": [],
          "required": true
        },
        "is_excluded": {
          "result": "INVALID",
          "evaluatedConstraints": [],
          "required": true
        },
        "concept-set-version-item": {
          "result": "INVALID",
          "evaluatedConstraints": [
            {
              "type": "objectQueryResult"
            }
          ],
          "required": true
        },
        "include_mapped": {
          "result": "INVALID",
          "evaluatedConstraints": [],
          "required": true
        }
      }
    }
    """
    api_name = 'set-omop-concept-set-version-item'
    # Commented out portions are part of the api definition
    d = {
        # "apiName": "set-omop-concept-set-version-item",
        # "description": "",
        # "rid": "ri.actions.main.action-type.56ce9a5b-c535-4413-be70-5526a8c152ed",
        # - Required params
        "parameters": {
            "include_descendants": include_descendants,
            # "include_descendants": {
            #   "description": "",
            #   "baseType": "Boolean"
            # TODO: is this supposed to be OMOP concept_id?
            # concept-set-version-item: More docs in function docstring.
            "concept-set-version-item": concept_set_version_item,
            # "concept-set-version-item": {
            #   "description": "",
            #   "baseType": "OntologyObject"
            "is_excluded": is_excluded,
            # "is_excluded": {
            #   "description": "",
            #   "baseType": "Boolean"
            "include_mapped": include_mapped,
            # "include_mapped": {
            #   "description": "",
            #   "baseType": "Boolean"
        }
    }
    return post(api_name, d, validate_first)


# api_name = 'edit-omop-concept-set-version-item'
# Currently unused, but will be useful for updates
def add_concept_via_edit(
    OmopConceptSetVersionItem: str, version: int, include_descendants=False, is_excluded=False, include_mapped=False,
    validate_first=VALIDATE_FIRST
) -> JSON_TYPE:
    """Create new concepets within concept set
    Non-required params set to `None`.
    """
    api_name = 'edit-omop-concept-set-version-item'
    d = {
        # "apiName": "edit-omop-concept-set-version-item",
        # "description": "",
        # "rid": "ri.actions.main.action-type.be264050-8b7f-44fe-9082-5fb4b748049a",
        "parameters": {
            "include_descendants": include_descendants,
              # "description": "If true, then these expression items will match on the selected OMOP Concepts, and all of their descendants.",
              # "baseType": "Boolean"
            "is_excluded": is_excluded,
              # "description": "If true, then any concepts matched will be added to the expression as exclusion rather than inclusion criteria. Exclusion criteria take precedence over inclusion criteria, in cases when a single OMOP Concept is affected by more than one entry in the OMOP Concept Set Expression.",
              # "baseType": "Boolean"
            "OmopConceptSetVersionItem": OmopConceptSetVersionItem,
              # "description": "",
              # "baseType": "OntologyObject"
            # version: More docs in function docstring.
            "version": version,
              # "description": "",
              # "baseType": "OntologyObject"
            "include_mapped": include_mapped,
              # "description": "If true, then these expression items will match on the selected OMOP Concepts, and all of the Non-Standard OMOP Concepts that map to them. If Include Descendants is also true, then this option will also include all OMOP Concepts that map to the included descendants. Setting this to true enables you to include non-standard Concepts in your Concept Set. Mapping is the process to transform one Concept into a Standard one. Read more: ohdsi.github.io/TheBookOfOhdsi/Cohorts.html#conceptSets and https://www.ohdsi.org/web/wiki/doku.php?id=documentation:vocabulary:mapping",
              # "baseType": "Boolean"
        }
    }
    return post(api_name, d, validate_first)


# code_set
# TODO: strange that new-parameter and new-parameter1 are required. I added arbitrary strings
def upload_draft_concept_set(
    concept_set: str, intention: str, domain_team: str = None, provenance: str = None, current_max_version: float = None
    , annotation: str = None, limitations: str = None, base_version: int = None, intended_research_project: str = None,
    version_id: int = None, authority: str = None, validate_first=VALIDATE_FIRST
) -> JSON_TYPE:
    """Create a new draft concept set. Wrapper for two API calls: (i) create-new-draft-omop-concept-set-version,
    (ii) finalize-draft-omop-concept-set-version

    :param domain_team (str): todo: domain_team: Not sure what to put here, but it is optional param, so I'm leaving blank - Joe
    :param annotation (str): todo: annotation: this should be moved into the new palantir-3-file data model, whatever that is - Joe
    :param intended_research_project (str): todo: intended_research_project: (a) default this to ENCLAVE_PROJECT_NAME in func, (b) do that here, (c) add it as a column to an updated palantir-3-file for the new api - Joe
    :param authority (str): todo: authority: Not sure what to put here, but it is optional param, so I'm leaving blank - Joe
    :param current_max_version (float): todo: current-max-version: Is it usefull to pass this? Is there any way to do a GET against the concept set container (name / ID) to find this out? Or would we have to track these versions in a local registry? - Joe
    :param base_version (int): # todo: base_version: Is it useful to pass this? how to know this? Depends on current-max-version as well. - Joe
    :param version_id (int): Equal to code_sets.codeset_id:
    https://unite.nih.gov/workspace/data-integration/dataset/preview/ri.foundry.main.dataset.7104f18e-b37c-419b-9755-a732bfa33b03/master

    Non-required params set to `None`.

    API call 1 of 2: create-new-draft-omop-concept-set-version
    Example curl:
        curl -H "Content-type: application/json" -H "Authorization: Bearer $OTHER_TOKEN" \
            https://unite.nih.gov/api/v1/ontologies/ri.ontology.main.ontology.00000000-0000-0000-0000-000000000000/actions/create-new-draft-omop-concept-set-version/validate \
            --data '{"parameters":{"domain-team":"just for testing of action api by Siggie" }}' | jq
        - Validate: Use above CURL
        - Apply: (replace /validate with /apply in above string)
        - This is a sign that it worked: "curl: (52) Empty reply from server"

    # todo: remove this when no longer needed for reference:
    Example validation:
    {
      "result": "INVALID",
      "submissionCriteria": [],
      "parameters": {
        "domain-team": {
          "result": "VALID",
          "evaluatedConstraints": [
            {
              "type": "objectQueryResult"
            }
          ],
          "required": false
        },
        "provenance": {
          "result": "VALID",
          "evaluatedConstraints": [],
          "required": false
        },
        "current-max-version": {
          "result": "VALID",
          "evaluatedConstraints": [],
          "required": false
        },
        "conceptSet": {
          "result": "INVALID",
          "evaluatedConstraints": [
            {
              "type": "objectQueryResult"
            }
          ],
          "required": true
        },
        "annotation": {
          "result": "VALID",
          "evaluatedConstraints": [],
          "required": false
        },
        "limitations": {
          "result": "VALID",
          "evaluatedConstraints": [],
          "required": false
        },
        "intention": {
          "result": "INVALID",
          "evaluatedConstraints": [
            {
              "type": "oneOf",
              "options": [
                {
                  "displayName": "",
                  "value": "Broad (sensitive)"
                },
                {
                  "displayName": "",
                  "value": "Narrow (specific)"
                },
                {
                  "displayName": "",
                  "value": "Mixed"
                }
              ],
              "otherValuesAllowed": true
            }
          ],
          "required": true
        },
        "baseVersion": {
          "result": "VALID",
          "evaluatedConstraints": [
            {
              "type": "objectQueryResult"
            }
          ],
          "required": false
        },
        "intended-research-project": {
          "result": "VALID",
          "evaluatedConstraints": [
            {
              "type": "objectQueryResult"
            }
          ],
          "required": false
        },
        "versionId": {
          "result": "VALID",
          "evaluatedConstraints": [],
          "required": false
        },
        "authority": {
          "result": "VALID",
          "evaluatedConstraints": [],
          "required": false
        }
      }
    }

    API call 2 of 2: finalize-draft-omop-concept-set-version
    # todo: add any further docs for this step here
    """
    api_name = 'create-new-draft-omop-concept-set-version'

    # Validate / warnings
    current_max_version_docstring = \
        "`current_max_version`: This must be set to the current maximum version number assigned to a version of this " \
        "concept set, or null if creating the first version of a concept set. If null, then baseVersion is not required"
    current_max_version_shared_warning_msg = \
        f'Attempting to upload, though if there is an error, this may be the cause. Original documentation for ' \
        f'`current_max_version`\n: {current_max_version_docstring}'
    if version_id <= 1 and current_max_version:
        print(f'Warning: `version_id` {version_id} appears to be first version, in which case `current_max_version`'
              f' should be `null` (`None` in Python). You passed {current_max_version} for `current_max_version`.\n'
              f'{current_max_version_shared_warning_msg}', file=sys.stderr)
    if base_version and not current_max_version:
        print(f'Warning: You passed a `base_version`, which is not required when there is no `current_max_version`.', file=sys.stderr)

    # Commented out portions are part of the api definition
    d = {
        # "apiName": api_name,
        # "description": "",
        # "rid": "ri.actions.main.action-type.fb260d04-b50e-4e29-9d39-6cce126fda7f",
        # - Required params
        "parameters": {
            "conceptSet": concept_set,
            # "conceptSet": {
            #   "description": "",
            #   "baseType": "OntologyObject"
            # conceptSet: Validate shows:
            #   "evaluatedConstraints": [{"type": "objectQueryResult"}],

            "intention": intention,
            # "intention": {
            #   "description": "",
            #   "baseType": "String"
        }
    }
    # - Optional params
    # "domain-team": {
    #   "description": "",
    #   "baseType": "OntologyObject"
    # todo: more info in function docstring
    if domain_team:
        d['parameters']['domain-team'] = domain_team

    # "provenance": {
    #   "description": "This field is optional, you will have a chance to fill this in later.",
    #   "baseType": "String"
    if provenance:
        d['parameters']['provenance'] = provenance

    # "current-max-version": {
    #   "description": "This must be set to the current maximum version number assigned to a version of this "
    #     "concept set, or null if creating the first version of a concept set. If null, then baseVersion is not "
    #     "required",
    #   "baseType": "Double"
    # todo: more info in function docstring
    if current_max_version:
        d['parameters']['current-max-version'] = current_max_version

    # "annotation": {
    #   "description": "",
    #   "baseType": "String"
    # todo: more info in function docstring
    if annotation:
        d['parameters']['annotation'] = annotation

    # "limitations": {
    #   "description": "This field is optional, you will have a chance to fill this in later.",
    #   "baseType": "String"
    if limitations:
        d['parameters']['limitations'] = limitations

    # "baseVersion": {
    #   "description": "",
    #   "baseType": "OntologyObject"
    # todo: more info in function docstring
    if base_version:
        d['parameters']['baseVersion'] = base_version

    # "intended-research-project": {
    #   "description": "",
    #   "baseType": "OntologyObject"
    # todo: more info in function docstring
    if intended_research_project:
        d['parameters']['intended-research-project'] = intended_research_project

    # "versionId": {
    #   "description": "",
    #   "baseType": "Integer"
    if version_id:  # == code_sets.codeset_id
        d['parameters']['versionId'] = version_id

    # "authority": {
    #   "description": "",
    #   "baseType": "String"
    # todo: more info in function docstring
    if authority:
        d['parameters']['authority'] = authority

    response: JSON_TYPE = post(api_name, d, validate_first)
    if 'errorCode' in response:
        print(response, file=sys.stderr)
        # todo: What can I add to help the user figure out what to do to fix, until API returns better responses?

    # TODO: strange that new-parameter and new-parameter1 are required. I added arbitrary strings
    response2: JSON_TYPE = post(
        api_name='finalize-draft-omop-concept-set-version',
        data={
            "parameters": {
                "new-parameter1": 'hello new-parameter1',  # required
                #   "description": "",
                #   "baseType": "String"
                "concept-set-container": concept_set,
                # "description": "",
                # "baseType": "OntologyObject"
                "version": version_id,
                # "description": "",
                # "baseType": "OntologyObject"
                # "currentMaxVersion": {
                #   "description": "",
                #   "baseType": "Double"
                "new-parameter": 'hello new-parameter',  # required
                #   "description": "",
                #   "baseType": "String"
            }
        },
        validate_first=validate_first)
    if 'errorCode' in response2:
        print(response, file=sys.stderr)
        # todo: What can I add to help the user figure out what to do to fix, until API returns better responses?

    if 'errorCode' in response or 'errorCode' in response2:
        print('This function upload_draft_concept_set() calls two endpoints. At least one of them errored. '
              'See response by endpoint below.', file=sys.stderr)
    return {'create-new-draft-omop-concept-set-version': response, 'finalize-draft-omop-concept-set-version': response}



# concept_set_container
def upload_concept_set(
    concept_set_id: str, intention: str, research_project: ENCLAVE_PROJECT_NAME, assigned_sme: str = None,
    assigned_informatician: str = None, validate_first=VALIDATE_FIRST
) -> JSON_TYPE:
    """Create a new concept set
    Non-required params set to `None`.

    :param research_project (str): todo: add it as a column to an updated palantir-3-file

    Example curl:
        curl -H "Content-type: application/json" -H "Authorization: Bearer $OTHER_TOKEN" \
            https://unite.nih.gov/api/v1/ontologies/ri.ontology.main.ontology.00000000-0000-0000-0000-000000000000/actions/create-new-concept-set/validate \
            --data '{"parameters":{"intention":"just for testing of action api by Siggie" }}' | jq
        - Validate: Use above CURL
        - Apply: (replace /validate with /apply in above string)
        - This is a sign that it worked: "curl: (52) Empty reply from server"

    todo: remove this when no longer needed for reference:
    Validation example:
    {
      "result": "VALID",
      "submissionCriteria": [],
      "parameters": {
        "assigned_sme": {
          "result": "VALID",
          "evaluatedConstraints": [
            {
              "type": "groupMember"
            }
          ],
          "required": false
        },
        "assigned_informatician": {
          "result": "VALID",
          "evaluatedConstraints": [
            {
              "type": "groupMember"
            }
          ],
          "required": false
        },
        "concept_set_id": {
          "result": "VALID",
          "evaluatedConstraints": [],
          "required": true
        },
        "intention": {
          "result": "VALID",
          "evaluatedConstraints": [
            {
              "type": "oneOf",
              "options": [
                {
                  "displayName": "",
                  "value": "Broad (sensitive)"
                },
                {
                  "displayName": "",
                  "value": "Narrow (specific)"
                },
                {
                  "displayName": "",
                  "value": "Mixed"
                }
              ],
              "otherValuesAllowed": true
            }
          ],
          "required": true
        },
        "research-project": {
          "result": "VALID",
          "evaluatedConstraints": [
            {
              "type": "objectQueryResult"
            }
          ],
          "required": true
        },
        "status": {
          "result": "VALID",
          "evaluatedConstraints": [
            {
              "type": "oneOf",
              "options": [
                {
                  "displayName": "",
                  "value": "Under Construction"
                }
              ],
              "otherValuesAllowed": false
            }
          ],
          "required": true
        },
        "stage": {
          "result": "VALID",
          "evaluatedConstraints": [
            {
              "type": "oneOf",
              "options": [
                {
                  "displayName": "",
                  "value": "Awaiting Editing"
                }
              ],
              "otherValuesAllowed": false
            }
          ],
          "required": true
        }
      }
    }
    """
    api_name = 'create-new-concept-set'
    # Commented out portions are part of the api definition
    d = {
        # "apiName": api_name,
        # "description": "Creates a new 'empty' Concept Set linked to a research project",
        # "rid": "ri.actions.main.action-type.ef6f89de-d5e3-450c-91ea-17132c8636ae",
        "parameters": {
            # - Required params
            "concept_set_id": concept_set_id,
            # "concept_set_id": {
            #     "description": "",
            #     "baseType": "String"
            "status": "Under Construction",
            # status: As of 2022/10/19, only 'Under Construction' is allowed
            # "status": {
            #     "description": "",
            #     "baseType": "String"
            "intention": intention,
            # "intention": {
            #     "description": "",
            #     "baseType": "String"
            "research-project": research_project,
            # "research-project": {
            #     "description": "Research project Concept Set is being created for",
            #     "baseType": "OntologyObject"
            "stage": "Awaiting Editing",
            # stage: As of 2022/10/19, only 'Awaiting Editing' is allowed
            # "stage": {
            #     "description": "",
            #     "baseType": "String"
        }
    }
    # - Optional params
    # "assigned_sme": {
    #     "description": "",
    #     "baseType": "String"
    if assigned_sme:
        d['parameters']['assigned_sme'] = assigned_sme
    # "assigned_informatician": {
    #     "description": "",
    #     "baseType": "String"
    if assigned_informatician:
        d['parameters']['assigned_informatician'] = assigned_informatician

    response: JSON_TYPE = post(api_name, d, validate_first)
    if 'errorCode' in response:
        print(response, file=sys.stderr)
        print('If above error message does not say what is wrong, it is probably the case that the `concept_set_id` '
              f'already exists. You passed: {concept_set_id}')
    return response


def make_request(api_name: str, data: Union[List, Dict] = None, validate=False, verbose=False) -> JSON_TYPE:
    """Passthrough for HTTP request
    If `data`, knows to do a POST. Otherwise does a GET.
    Enclave docs:
      https://www.palantir.com/docs/foundry/api/ontology-resources/objects/list-objects/
      https://www.palantir.com/docs/foundry/api/ontology-resources/object-types/list-object-types/
    """
    headers = {
        # todo: When/if @Amin et al allow enclave service token to write to the new API, change this back from.
        # "authorization": f"Bearer {config['PALANTIR_ENCLAVE_AUTHENTICATION_BEARER_TOKEN']}",
        "authorization": f"Bearer {config['OTHER_TOKEN']}",
        "Content-type": "application/json",

    }
    ontology_rid = config['ONTOLOGY_RID']
    api_path = f'/api/v1/ontologies/{ontology_rid}/actions/{api_name}/'
    api_path += 'validate' if validate else 'apply'
    url = f'https://{config["HOSTNAME"]}{api_path}'
    if verbose:
        print(f'make_request: {api_path}\n{url}')

    try:
        if data:
            response = requests.post(url, headers=headers, json=data)
        else:
            response = requests.get(url, headers=headers)
        response.raise_for_status()
    except BaseException as err:
        print(f"Unexpected {type(err)}: {str(err)}", file=sys.stderr)

    # noinspection PyUnboundLocalVariable
    response_json: JSON_TYPE = response.json()
    return response_json


def get(api_name: str, validate=False) -> JSON_TYPE:
    """For GET request"""
    return make_request(api_name, validate=validate)


def post(api_name: str, data: Dict, validate_first=VALIDATE_FIRST) -> JSON_TYPE:
    """For POST request"""
    if validate_first:
        response: JSON_TYPE = make_request(api_name, data, validate=True)
        if not ('result' in response and response['result'] == 'VALID'):
            print(f'Failure: {api_name}\n', response, file=sys.stderr)
            return response
    return make_request(api_name, data, validate=False)
