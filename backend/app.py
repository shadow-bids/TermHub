"""TermHub backend

Resources
- https://github.com/tiangolo/fastapi
"""
import json
import os
from pathlib import Path
from subprocess import call as sp_call
from typing import Any, Dict, List, Union, Set
from functools import cache

import numpy as np
import pandas as pd
import uvicorn
import urllib.parse
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel

from enclave_wrangler.config import OUTDIR_DATASETS_TRANSFORMED, OUTDIR_OBJECTS
from enclave_wrangler.dataset_upload import upload_new_container_with_concepts, upload_new_cset_version_with_concepts
from enclave_wrangler.datasets import run_favorites as update_termhub_csets
from enclave_wrangler.new_enclave_api import make_read_request

from backend.db.mysql_utils import sql_query, get_mysql_connection

CON = get_mysql_connection()  # using a global connection object is probably a terrible idea, but
                              # shouldn't matter much until there are multiple users on the same server
DEBUG = True
PROJECT_DIR = Path(os.path.dirname(__file__)).parent
# TODO: Replace LFS implementation here with DB
# TODO: initialize if doesn't exist on start
# GLOBAL_DATASET_NAMES = list(FAVORITE_DATASETS.keys()) + ['concept_relationship_is_a']
GLOBAL_DATASET_NAMES = [
    'concept_set_members',
    'concept',
    'concept_relationship_subsumes_only',
    'concept_set_container',
    'code_sets',
    'concept_set_version_item',
    'deidentified_term_usage_by_domain_clamped',
    'concept_set_counts_clamped'
]
GLOBAL_OBJECT_DATASET_NAMES = [
    'researcher'
]
DS = None  # Contains all the datasets as a dict
DS2 = None  # Contains all datasets, transformed datasets, and a few functions as a namespace


# Globals --------------------------------------------------------------------------------------------------------------
def load_dataset(ds_name, is_object=False) -> pd.DataFrame:
    """Load a local dataset CSV as a pandas DF"""
    csv_dir = OUTDIR_DATASETS_TRANSFORMED if not is_object else os.path.join(OUTDIR_OBJECTS, ds_name)
    path = os.path.join(csv_dir, ds_name + '.csv') if not is_object else os.path.join(csv_dir, 'latest.csv')
    print(f'loading: {path}')
    try:
        # tried just reading into pandas from sql tables --- incredibly slow!
        # ds = pd.read_sql_table(ds_name, CON, 'termhub_n3c')
        ds = pd.read_csv(path, keep_default_na=False)
    except Exception as err:
        print(f'failed loading {path}')
        raise err
    return ds


class Bunch(object):    # dictionary to namespace, a la https://stackoverflow.com/a/2597440/1368860
  def __init__(self, adict):
    self.__dict__.update(adict)


def cnt(vals):
    return len(set(vals))


def commify(n):
    return f'{n:,}'


def filter(msg, ds, dfname, func, cols):
    df = ds.__dict__[dfname]
    before = { col: cnt(df[col]) for col in cols }

    ds.__dict__[dfname] = func(df)
    if ds.__dict__[dfname].equals(df):
        log_counts(f'{msg}. No change.', **before)
    else:
        log_counts(f'{msg}. Before', **before)
        after = { col: cnt(df[col]) for col in cols }
        log_counts(f'{msg}. After', **after)
        # change = { col: (after[col] - before[col]) / before[col] for col in cols }


def _log_counts():
    msgs = []
    def __log_counts(msg=None, concept_set_name=None, codeset_id=None, concept_id=None, print=False):
        if msg:
            msgs.append([msg, *[int(n) if n else None for n in [concept_set_name, codeset_id, concept_id]]])
        if (print):
          pdump(msgs)
        return msgs
    return __log_counts


log_counts = _log_counts()


def load_globals():
    """
    expose tables and other stuff in namespace for convenient reference
        links                   # concept_relationship grouped by concept_id_1, subsumes only
        child_cids()            # function returning all the concept_ids that are
                                #   children (concept_id_1) of a concept_id
        connect_children()      # function returning concept hierarchy. see #139
                                #   (https://github.com/jhu-bids/TermHub/issues/139)
                                #   currently doing lists of tuples, will probably
                                #   switch to dict of dicts
    """
    ds = Bunch(DS)

    # TODO: try this later. will require filtering other stuff also? This will be useful for provenance
    # ds.data_messages = []
    other_msgs = []

    log_counts('concept_set_container', concept_set_name=cnt(ds.concept_set_container.concept_set_name))

    # s = run_sql(CON, 'select count(*) from concept_set_container')
    # print(s)

    log_counts('code_sets',
               concept_set_name=cnt(ds.code_sets.concept_set_name),
               codeset_id=cnt(ds.code_sets.codeset_id))
    log_counts('concept_set_members',
               concept_set_name=cnt(ds.concept_set_members.concept_set_name),
               codeset_id=cnt(ds.concept_set_members.codeset_id),
               concept_id=cnt(ds.concept_set_members.concept_id))
    log_counts('concept_set_version_item',
               concept_set_name=cnt(ds.concept_set_members.concept_set_name),
               codeset_id=cnt(ds.concept_set_version_item.codeset_id),
               concept_id=cnt(ds.concept_set_version_item.concept_id))
    log_counts('intersection(containers, codesets)',
               concept_set_name=len(set.intersection(set(ds.concept_set_container.concept_set_name),
                                                     set(ds.code_sets.concept_set_name))))
    log_counts('intersection(codesets, members, version_items)',
               codeset_id=len(set.intersection(set(ds.code_sets.codeset_id),
                                               set(ds.concept_set_members.codeset_id),
                                               set(ds.concept_set_version_item.codeset_id))))
    log_counts('intersection(codesets, version_items)',
               codeset_id=len(set.intersection(set(ds.code_sets.codeset_id),
                                               set(ds.concept_set_version_item.codeset_id))))
    log_counts('intersection(members, version_items)',
               codeset_id=len(set.intersection(set(ds.concept_set_members.codeset_id),
                                               set(ds.concept_set_version_item.codeset_id))),
               concept_id=len(set.intersection(set(ds.concept_set_members.concept_id),
                                               set(ds.concept_set_version_item.concept_id))))

    codeset_ids = set(ds.concept_set_version_item.codeset_id)

    if len(set(ds.code_sets.codeset_id).difference(codeset_ids)):
      filter('weird that there would be versions (in code_sets and concept_set_members) '
                        'that have nothing in concept_set_version_item...filtering those out',
             ds, 'code_sets', lambda df: df[df.codeset_id.isin(codeset_ids)], ['codeset_id'])

    if len(ds.concept_set_container) > cnt(ds.concept_set_container.concept_set_name):
      filter('concept_set_containers have duplicate items with different created_at and/or created_by. deleting all but most recent',
             ds, 'concept_set_container',
             lambda df: df.sort_values('created_at').groupby('concept_set_name').agg(lambda g: g.head(1)).reset_index(),
             ['concept_set_name'])


    # no change (2022-10-23):
    filter('concept_set_container filtered to exclude archived',
           ds, 'concept_set_container', lambda df: df[~ df.archived], ['concept_set_name'])

    #
    filter('concept_set_members filtered to exclude archived',
           ds, 'concept_set_members', lambda df: df[~ df.archived], ['codeset_id', 'concept_id'])

    concept_set_names = set.intersection(
                            set(ds.concept_set_container.concept_set_name),
                            set(ds.code_sets.concept_set_name))

    # csm_archived_names = set(DS['concept_set_members'][DS['concept_set_members'].archived].concept_set_name)
    # concept_set_names = concept_set_names.difference(csm_archived_names)

    # no change (2022-10-23):
    filter('concept_set_container filtered to have matching code_sets/versions',
           ds, 'concept_set_container', lambda df: df[df.concept_set_name.isin(concept_set_names)], ['concept_set_name'])

    filter('code_sets filtered to have matching concept_set_container',
           ds, 'code_sets', lambda df: df[df.concept_set_name.isin(concept_set_names)], ['concept_set_name'])

    codeset_ids = set.intersection(set(ds.code_sets.codeset_id),
                                   set(ds.concept_set_version_item.codeset_id))
    filter(
        'concept_set_members filtered to filtered code_sets', ds, 'concept_set_members',
        lambda df: df[df.codeset_id.isin(set(ds.code_sets.codeset_id))], ['codeset_id', 'concept_id'])

    # Filters out any concepts/concept sets w/ no name
    filter('concept_set_members filtered to exclude concept sets with empty names',
            ds, 'concept_set_members',
           lambda df: df[~df.archived],
           ['codeset_id', 'concept_id'])

    filter('concept_set_members filtered to exclude archived concept set.',
           ds, 'concept_set_members',
           lambda df: df[~df.archived],
           ['codeset_id', 'concept_id'])

    ds.concept_relationship = ds.concept_relationship_subsumes_only
    other_msgs.append('only using subsumes relationships in concept_relationship')

    # I don't know why, there's a bunch of codesets that have no concept_set_version_items:
    # >>> len(set(ds.concept_set_members.codeset_id))
    # 3733
    # >>> len(set(ds.concept_set_version_item.codeset_id))
    # 3021
    # >>> len(set(ds.concept_set_members.codeset_id).difference(set(ds.concept_set_version_item.codeset_id)))
    # 1926
    # should just toss them, right?

    # len(set(ds.concept_set_members.concept_id))             1,483,260
    # len(set(ds.concept_set_version_item.concept_id))          429,470
    # len(set(ds.concept_set_version_item.concept_id)
    #     .difference(set(ds.concept_set_members.concept_id)))   19,996
    #
    member_concepts = set(ds.concept_set_members.concept_id)
        #.difference(set(ds.concept_set_version_item))

    ds.concept_set_version_item = ds.concept_set_version_item[
        ds.concept_set_version_item.concept_id.isin(member_concepts)]

    # only need these two columns now:
    ds.concept_set_members = ds.concept_set_members[['codeset_id', 'concept_id']]

    ds.all_related_concepts = set(ds.concept_relationship.concept_id_1).union(
                                set(ds.concept_relationship.concept_id_2))
    all_findable_concepts = member_concepts.union(ds.all_related_concepts)

    ds.concept.drop(['domain_id', 'vocabulary_id', 'concept_class_id', 'standard_concept', 'concept_code',
                      'invalid_reason', ], inplace=True, axis=1)

    ds.concept = ds.concept[ds.concept.concept_id.isin(all_findable_concepts)]

    ds.links = ds.concept_relationship.groupby('concept_id_1')
    # ds.all_concept_relationship_cids = set(ds.concept_relationship.concept_id_1).union(set(ds.concept_relationship.concept_id_2))

    @cache
    def child_cids(cid):
        """Return list of `concept_id_2` for each `concept_id_1` (aka all its children)"""
        if cid in ds.links.groups.keys():
            return [int(c) for c in ds.links.get_group(cid).concept_id_2.unique() if c != cid]
    ds.child_cids = child_cids

    # @cache
    def connect_children(pcid, cids):  # how to declare this should be tuple of int or None and list of ints
        if not cids:
            return None
        pcid in cids and cids.remove(pcid)
        pcid_kids = {int(cid): child_cids(cid) for cid in cids}
        # pdump({'kids': pcid_kids})
        return {cid: connect_children(cid, kids) for cid, kids in pcid_kids.items()}

    ds.connect_children = connect_children

    # Take codesets, and merge on container. Add to each version.
    # Some columns in codeset and container have the same name, so suffix is needed to distinguish them
    # ...The merge on `concept_set_members` is used for concept counts for each codeset version.
    #   Then adding cset usage counts
    all_csets = (
        ds
            .code_sets.merge(ds.concept_set_container, suffixes=['_version', '_container'],
                             on='concept_set_name')
            .merge(ds.concept_set_members
                        .groupby('codeset_id')['concept_id']
                            .nunique()
                            .reset_index()
                            .rename(columns={'concept_id': 'concepts'}), on='codeset_id')
            .merge(ds.concept_set_counts_clamped, on='codeset_id')
    )
    """
    all_csets columns:
    ['codeset_id', 'concept_set_version_title', 'project',
       'concept_set_name', 'source_application', 'source_application_version',
       'created_at_version', 'atlas_json', 'is_most_recent_version', 'version',
       'comments', 'intention_version', 'limitations', 'issues',
       'update_message', 'status_version', 'has_review', 'reviewed_by',
       'created_by_version', 'provenance', 'atlas_json_resource_url',
       'parent_version_id', 'authoritative_source', 'is_draft',
       'concept_set_id', 'project_id', 'assigned_informatician',
       'assigned_sme', 'status_container', 'stage', 'intention_container',
       'n3c_reviewer', 'alias', 'archived', 'created_by_container',
       'created_at_container', 'concepts', 'approx_distinct_person_count',
       'approx_total_record_count'],
    had been dropping all these and all the research UIDs... should
      start doing stuff with that info.... had just been looking for ways 
      to make data smaller.... 
    
    all_csets = all_csets.drop([
      'parent_version_id', 'concept_set_name', 'source_application', 
      'is_draft', 'project', 'atlas_json', 'created_at_container', 
      'source_application_version', 'version', 'comments', 'alias', 
      'concept_set_id', 'created_at_version', 'atlas_json_resource_url'])
    """

    all_csets = all_csets.drop_duplicates()
    ds.all_csets = all_csets

    print('added usage counts to code_sets')

    """
        Term usage is broken down by domain and some concepts appear in multiple domains.
        (each concept has only one domain_id in the concept table, but the same concept might
        appear in condition_occurrence and visit and procedure, so it would have usage counts
        in multiple domains.) We can sum total_counts across domain, but not distinct_person_counts
        (possible double counting). So, for now at least, distinct_person_count will appear as a 
        comma-delimited list of counts -- which, of course, makes it hard to use in visualization.
        Maybe we should just use the domain with the highest distinct person count? Not sure.
    """
    # df = df[df.concept_id.isin([9202, 9201])]
    domains = {
        'drug_exposure': 'd',
        'visit_occurrence': 'v',
        'observation': 'o',
        'condition_occurrence': 'c',
        'procedure_occurrence': 'p',
        'measurement': 'm'
    }
    # ds.deidentified_term_usage_by_domain_clamped['domain'] = \
    #     [domains[d] for d in ds.deidentified_term_usage_by_domain_clamped.domain]

    g = ds.deidentified_term_usage_by_domain_clamped.groupby(['concept_id'])
    concept_usage_counts = (
        g.size().to_frame(name='domain_cnt')
         .join(g.agg(
                    total_count=('total_count', sum),
                    domain=('domain', ','.join),
                    distinct_person_count=('distinct_person_count', lambda x: ','.join([str(c) for c in x]))
                ))
        .reset_index())
    print('combined usage counts across domains')

    # c = ds.concept.reset_index()
    # cs = c[c.concept_id.isin([9202, 9201, 4])]

    # h = [r[1] for r in ds.deidentified_term_usage_by_domain_clamped.head(3).iterrows()]
    # [{r.domain: {'records': r.total_count, 'patients': r.distinct_person_count}} for r in h]
    ds.concept = (
        ds.concept.drop(['valid_start_date','valid_end_date'], axis=1)
            .merge(concept_usage_counts, on='concept_id', how='left')
            .fillna({'domain_cnt': 0, 'domain': '', 'total_count': 0, 'distinct_person_count': 0})
            .astype({'domain_cnt': int, 'total_count': int})
            # .set_index('concept_id')
    )
    print('Done building global ds objects')

    return ds


def disabling_globals():
    # todo: consider: run 2 backend servers, 1 to hold the data and 1 to service requests / logic? probably.
    # TODO: #2: remove try/except when git lfs fully set up
    # todo: temp until we decide if this is the correct way
    try:
        DS = {
            **{name: load_dataset(name) for name in GLOBAL_DATASET_NAMES},
            **{name: load_dataset(name, is_object=True) for name in GLOBAL_OBJECT_DATASET_NAMES},
        }
        DS2 = load_globals()
        #  TODO: Fix this warning? (Joe: doing so will help load faster, actually)
        #   DtypeWarning: Columns (4) have mixed types. Specify dtype option on import or set low_memory=False.
        #   keep_default_na fixes some or all the warnings, but doesn't manage dtypes well.
        #   did this in termhub-csets/datasets/fixing-and-paring-down-csv-files.ipynb:
        #   csm = pd.read_csv('./concept_set_members.csv',
        #                    # dtype={'archived': bool},    # doesn't work because of missing values
        #                   converters={'archived': lambda x: x and True or False}, # this makes it a bool field
        #                   keep_default_na=False)
    except FileNotFoundError:
        # todo: what if they haven't downloaded? maybe need to ls files and see if anything needs to be downloaded first
        # TODO: objects should be updated too
        update_termhub_csets(transforms_only=True)
        DS = {
            **{name: load_dataset(name) for name in GLOBAL_DATASET_NAMES},
            **{name: load_dataset(name, is_object=True) for name in GLOBAL_OBJECT_DATASET_NAMES},
        }
        DS2 = load_globals()
    print(f'Favorite datasets loaded: {list(DS.keys())}')


# Utility functions ----------------------------------------------------------------------------------------------------
# @cache
def data_stuff_for_codeset_ids(codeset_ids):
    """
    for specific codeset_ids:
        subsets of tables:
            df_code_set_i
            df_concept_set_members_i
            df_concept_relationship_i
        and other stuff:
            concept_ids             # union of all the concept_ids across the requested codesets
            related                 # sorted list of related concept sets
            codesets_by_concept_id  # lookup codeset_ids a concept_id belongs to (in dsi instead of ds because of possible performance impacts)
            top_level_cids          # concepts in selected codesets that have no parent concepts in this group
            cset_name_columns       #

    """
    dsi = Bunch({})

    print(f'data_stuff_for_codeset_ids({codeset_ids})')

    # Vocab table data
    dsi.code_sets_i = DS2.code_sets[DS2.code_sets['codeset_id'].isin(codeset_ids)]
    dsi.concept_set_members_i = DS2.concept_set_members[DS2.concept_set_members['codeset_id'].isin(codeset_ids)]
    # - version items
    dsi.concept_set_version_item_i = DS2.concept_set_version_item[DS2.concept_set_version_item['codeset_id'].isin(codeset_ids)]
    flags = ['includeDescendants', 'includeMapped', 'isExcluded']
    dsi.concept_set_version_item_i = dsi.concept_set_version_item_i[['codeset_id', 'concept_id', *flags]]
    # doesn't work if df is empty
    if len(dsi.concept_set_version_item_i):
      dsi.concept_set_version_item_i['item_flags'] = dsi.concept_set_version_item_i.apply(
        lambda row: (', '.join([f for f in flags if row[f]])), axis=1)
    else:
      dsi.concept_set_version_item_i = dsi.concept_set_version_item_i.assign(item_flags='')
    dsi.concept_set_version_item_i = dsi.concept_set_version_item_i[['codeset_id', 'concept_id', 'item_flags']]
    # - cset member items
    dsi.cset_members_items = \
      dsi.concept_set_members_i.assign(csm=True).merge(
        dsi.concept_set_version_item_i.assign(item=True),
        on=['codeset_id', 'concept_id'], how='outer', suffixes=['_l','_r']
      ).fillna({'item_flags': '', 'csm': False, 'item': False})

    # - selected csets and relationships
    selected_concept_ids: Set[int] = set.union(set(dsi.cset_members_items.concept_id))
    dsi.concept_relationship_i = DS2.concept_relationship[
        (DS2.concept_relationship.concept_id_1.isin(selected_concept_ids)) &
        (DS2.concept_relationship.concept_id_2.isin(selected_concept_ids)) &
        (DS2.concept_relationship.concept_id_1 != DS2.concept_relationship.concept_id_2)
        # & (ds.concept_relationship.relationship_id == 'Subsumes')
        ]

    # Get related codeset IDs
    related_codeset_ids: Set[int] = set(DS2.concept_set_members[
        DS2.concept_set_members.concept_id.isin(selected_concept_ids)].codeset_id)
    dsi.related_csets = (
      DS2.all_csets[DS2.all_csets['codeset_id'].isin(related_codeset_ids)]
        .merge(DS2.concept_set_members, on='codeset_id')
        .groupby(list(DS2.all_csets.columns))['concept_id']
        .agg(intersecting_concepts=lambda x: len(set(x).intersection(selected_concept_ids)))
        .reset_index()
        .convert_dtypes({'intersecting_concept_ids': 'int'})
        .assign(recall=lambda row: row.intersecting_concepts / len(selected_concept_ids),
                precision=lambda row: row.intersecting_concepts / row.concepts,
                selected= lambda row: row.codeset_id.isin(codeset_ids))
        .sort_values(by=['selected', 'concepts'], ascending=False)
    )
    dsi.selected_csets = dsi.related_csets[dsi.related_csets['codeset_id'].isin(codeset_ids)]

    # Researchers
    researcher_cols = ['created_by_container', 'created_by_version', 'assigned_sme', 'reviewed_by', 'n3c_reviewer',
                       'assigned_informatician']
    researcher_ids = []
    for i, row in dsi.selected_csets.iterrows():
      for _id in [row[col] for col in researcher_cols if hasattr(row, col) and row[col]]:
        researcher_ids.append(_id)
    researcher_ids: List[str] = list(set(researcher_ids))
    researchers: List[Dict] = DS2.researcher[DS2.researcher['multipassId'].isin(researcher_ids)].to_dict(orient='records')
    dsi.selected_csets['researchers'] = researchers

    # Selected cset RIDs
    dsi.selected_csets['rid'] = [get_container(name)['rid'] for name in dsi.selected_csets.concept_set_name]

    # Get relationships for selected code sets
    dsi.links = dsi.concept_relationship_i.groupby('concept_id_1')

    # Get child `concept_id`s
    @cache
    def child_cids(cid):
        """Closure for geting child concept IDs"""
        if cid in dsi.links.groups.keys():
            return [int(c) for c in dsi.links.get_group(cid).concept_id_2.unique() if c != cid]
    dsi.child_cids = child_cids

    # @cache
    def connect_children(pcid, cids):  # how to declare this should be tuple of int or None and list of ints
        if not cids:
            return None
        pcid in cids and cids.remove(pcid)
        pcid_kids = {int(cid): child_cids(cid) for cid in cids}
        # pdump({'kids': pcid_kids})
        return {cid: connect_children(cid, kids) for cid, kids in pcid_kids.items()}
    dsi.connect_children = connect_children

    # Top level concept IDs for the root of our flattened hierarchy
    dsi.top_level_cids = (set(selected_concept_ids).difference(set(dsi.concept_relationship_i.concept_id_2)))

    dsi.hierarchy = h = dsi.connect_children(-1, dsi.top_level_cids)

    leaf_cids = set([])
    if h:
      leaf_cids = set([int(str(k).split('.')[-1]) for k in pd.json_normalize(h).to_dict(orient='records')[0].keys()])
    dsi.concepts = DS2.concept[DS2.concept.concept_id.isin(leaf_cids.union(set(dsi.cset_members_items.concept_id)))]

    return dsi

@cache
def parse_codeset_ids(qstring):
    if not qstring:
        return []
    requested_codeset_ids = qstring.split('|')
    requested_codeset_ids = [int(x) for x in requested_codeset_ids]
    return requested_codeset_ids

# Routes ---------------------------------------------------------------------------------------------------------------
APP = FastAPI()
APP.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_methods=['*'],
    allow_headers=['*']
)
APP.add_middleware(GZipMiddleware, minimum_size=1000)


@APP.get("/")
def read_root():
    """Root route"""
    # noinspection PyUnresolvedReferences
    url_list = [{"path": route.path, "name": route.name} for route in APP.routes]
    return url_list


@APP.get("/get-all-csets")
def get_all_csets() -> Union[Dict, List]:
  # this returns 4,327 rows. the old one below returned 3,127 rows
  # TODO: figure out why and if all_csets query in ddl.sql needs to be fixed

  return sql_query(
    CON, """ 
    SELECT codeset_id,
          concept_set_version_title,
          concepts
    FROM all_csets""")
  # smaller = DS2.all_csets[['codeset_id', 'concept_set_version_title', 'concepts']]
  # return smaller.to_dict(orient='records')


# TODO: the following is just based on concept_relationship
#       should also check whether relationships exist in concept_ancestor
#       that aren't captured here
# TODO: Add concepts outside the list of codeset_ids?
#       Or just make new issue for starting from one cset or concept
#       and fanning out to other csets from there?
# Example: http://127.0.0.1:8000/cr-hierarchy?codeset_id=818292046&codeset_id=484619125&codeset_id=400614256
@APP.get("/selected-csets")
def selected_csets(codeset_id: Union[str, None] = Query(default=''), ) -> Dict:
  requested_codeset_ids = parse_codeset_ids(codeset_id)
  return sql_query(CON, """
      SELECT *
      FROM all_csets
      WHERE codeset_id IN (:codeset_ids);""",
      {'codeset_ids': ','.join([str(id) for id in requested_codeset_ids])})


@APP.get("/cr-hierarchy")  # maybe junk, or maybe start of a refactor of above
def cr_hierarchy( rec_format: str='default', codeset_id: Union[str, None] = Query(default=''), ) -> Dict:

    # print(ds) uncomment just to put ds in scope for looking at in debugger
    requested_codeset_ids = parse_codeset_ids(codeset_id)
    # A namespace (like `ds`) specifically for these codeset IDs.
    dsi = data_stuff_for_codeset_ids(requested_codeset_ids)

    result = {
              # 'all_csets': dsi.all_csets.to_dict(orient='records'),
              'related_csets': dsi.related_csets.to_dict(orient='records'),
              'selected_csets': dsi.selected_csets.to_dict(orient='records'),
              # 'concept_set_members_i': dsi.concept_set_members_i.to_dict(orient='records'),
              # 'concept_set_version_item_i': dsi.concept_set_version_item_i.to_dict(orient='records'),
              'cset_members_items': dsi.cset_members_items.to_dict(orient='records'),
              'hierarchy': dsi.hierarchy,
              'concepts': dsi.concepts.to_dict(orient='records'),
              'data_counts': log_counts(),
    }
    return result


@APP.get("/cset-download")  # maybe junk, or maybe start of a refactor of above
def cset_download(codeset_id: int) -> Dict:
  dsi = data_stuff_for_codeset_ids([codeset_id])

  concepts = DS2.concept[DS2.concept.concept_id.isin(set(dsi.cset_members_items.concept_id))]
  cset = DS2.all_csets[DS2.all_csets.codeset_id == codeset_id].to_dict(orient='records')[0]
  cset['concept_count'] = cset['concepts']
  cset['concepts'] = concepts.to_dict(orient='records')
  return cset


@cache
def get_container(concept_set_name):
    """This is for getting the RID of a dataset. This is available via the ontology API, not the dataset API.
    TODO: This needs caching, but the @cache decorator is not working."""
    return make_read_request(f'objects/OMOPConceptSetContainer/{urllib.parse.quote(concept_set_name)}')

# todo: Some redundancy. (i) should only need concept_set_name once
class UploadNewCsetVersionWithConcepts(BaseModel):
    """Schema for route: /upload-new-cset-version-with-concepts

    Upload a concept set version along with its concepts.

    This schema is for POSTing to a FastAPI route.

    Schema:
    :param version_with_concepts (Dict): Has the following schema: {
        'omop_concepts': [
          {
            'concept_id' (int) (required):
            'includeDescendants' (bool) (required):
            'isExcluded' (bool) (required):
            'includeMapped' (bool) (required):
            'annotation' (str) (optional):
          }
        ],
        'provenance' (str) (required):
        'concept_set_name' (str) (required):
        'annotation' (str) (optional): Default:`'Curated value set: ' + version['concept_set_name']`
        'limitations' (str) (required):
        'intention' (str) (required):
        'intended_research_project' (str) (optional): Default:`ENCLAVE_PROJECT_NAME`
        'codeset_id' (int) (required): Default:Will ge generated if not passed.
    }

    # TODO: verify that this example is correct
    Example:
    {
        "omop_concepts": [
            {
              "concept_id": 45259000,
              "includeDescendants": true,
              "isExcluded": false,
              "includeMapped": true,
              "annotation": "This is my concept annotation."
            }
        ],
        "provenance": "Created through TermHub.",
        "concept_set_name": "My test concept set",
        "limitations": "",
        "intention": ""
    }
    """
    omop_concepts: List[Dict]
    provenance: str
    concept_set_name: str
    limitations: str
    intention: str


# TODO #123: add baseVersion: the version that the user starts off from in order to create their own new concept set
#  ...version. I need to add the ability to get arbitrary args (*args) including baseVersion, here in these routes and
#  ...in the other functions.
@APP.post("/upload-new-cset-version-with-concepts")
def route_upload_new_cset_version_with_concepts(d: UploadNewCsetVersionWithConcepts) -> Dict:
    """Upload new version of existing container, with concepets"""
    # TODO: Persist: see route_upload_new_container_with_concepts() for more info
    # result = csets_update(dataset_path='', row_index_data_map={})

    # todo: this is redundant. need to flesh out func param arity in various places
    response = upload_new_cset_version_with_concepts({
        'omop_concepts': d.omop_concepts,
        'provenance': d.provenance,
        'concept_set_name': d.concept_set_name,
        'limitations': d.limitations,
        'intention': d.intention})

    return {}  # todo: return. should include: assigned codeset_id's


# todo: Some redundancy. (i) should only need concept_set_name once
class UploadNewContainerWithConcepts(BaseModel):
    """Schema for route: /upload-new-container-with-concepts

    Upload a concept set container, along with versions version which include concepts.

    This schema is for POSTing to a FastAPI route.

    Schema:
    Should be JSON with top-level keys: container, versions_with_concepts

    :param container (Dict): Has the following keys:
        concept_set_name (str) (required):
        intention (str) (required):
        research_project (str) (required): Default:`ENCLAVE_PROJECT_NAME`
        assigned_sme (str) (optional): Default:`PALANTIR_ENCLAVE_USER_ID_1`
        assigned_informatician (str) (optional): Default:`PALANTIR_ENCLAVE_USER_ID_1`

    :param versions_with_concepts (List[Dict]): Has the following schema: [
      {
        'omop_concepts': [
          {
            'concept_id' (int) (required):
            'includeDescendants' (bool) (required):
            'isExcluded' (bool) (required):
            'includeMapped' (bool) (required):
            'annotation' (str) (optional):
          }
        ],
        'provenance' (str) (required):
        'concept_set_name' (str) (required):
        'annotation' (str) (optional): Default:`'Curated value set: ' + version['concept_set_name']`
        'limitations' (str) (required):
        'intention' (str) (required):
        'intended_research_project' (str) (optional): Default:`ENCLAVE_PROJECT_NAME`
        'codeset_id' (int) (required): Will be generated if not passed.
      }
    ]

    Example:
    {
      "container": {
        "concept_set_name": "My test concept set",
        "intention": "",
        "research_project": "",
        "assigned_sme": "",
        "assigned_informatician": ""
      },
      "versions_with_concepts": [{
        "omop_concepts": [
            {
              "concept_id": 45259000,
              "includeDescendants": true,
              "isExcluded": false,
              "includeMapped": true,
              "annotation": "This is my concept annotation."
            }
        ],
        "provenance": "Created through TermHub.",
        "concept_set_name": "My test concept set",
        "limitations": "",
        "intention": ""
      }]
    }
    """
    container: Dict
    versions_with_concepts: List[Dict]


# TODO: see todo '#123'
@APP.post("/upload-new-container-with-concepts")
def route_upload_new_container_with_concepts(d: UploadNewContainerWithConcepts) -> Dict:
    """Upload new container with concepts"""
    # TODO: Persist
    #  - call the function i defined for updating local git stuff. persist these changes and patch etc
    #     dataset_path: File path. Relative to `/termhub-csets/datasets/`
    #     row_index_data_map: Keys are integers of row indices in the dataset. Values are dictionaries, where keys are the
    #       name of the fields to be updated, and values contain the values to update in that particular cell."""
    #  - csets_update() doesn't meet exact needs. not actually updating to an existing index. adding a new row.
    #    - soution: can set index to -1, perhaps, to indicate that it is a new row
    #    - edge case: do i need to worry about multiple drafts at this point? delete if one exists? keep multiple? or at upload time
    #    ...should we update latest and delete excess drafts if exist?
    #  - git/patch changes (do this inside csets_update()): https://github.com/jhu-bids/TermHub/issues/165#issuecomment-1276557733
    # result = csets_update(dataset_path='', row_index_data_map={})

    response = upload_new_container_with_concepts(
        container=d.container,
        versions_with_concepts=d.versions_with_concepts)

    return {}  # todo: return. should include: assigned codeset_id's


# TODO: figure out where we want to put this. models.py? Create route files and include class along w/ route func?
# TODO: Maybe change to `id` instead of row index
class CsetsGitUpdate(BaseModel):
    """Update concept sets.
    dataset_path: File path. Relative to `/termhub-csets/datasets/`
    row_index_data_map: Keys are integers of row indices in the dataset. Values are dictionaries, where keys are the
      name of the fields to be updated, and values contain the values to update in that particular cell."""
    dataset_path: str = ''
    row_index_data_map: Dict[int, Dict[str, Any]] = {}


# TODO: (i) move most of this functionality out of route into separate function (potentially keeping this route which
#  simply calls that function as well), (ii) can then connect that function as step in the routes that coordinate
#  enclave uploads
# TODO: git/patch changes: https://github.com/jhu-bids/TermHub/issues/165#issuecomment-1276557733
def csets_git_update(dataset_path: str, row_index_data_map: Dict[int, Dict[str, Any]]) -> Dict:
    """Update cset dataset. Works only on tabular files."""
    # Vars
    result = 'success'
    details = ''
    cset_dir = os.path.join(PROJECT_DIR, 'termhub-csets')
    path_root = os.path.join(cset_dir, 'datasets')

    # Update cset
    # todo: dtypes need to be registered somewhere. perhaps a <CSV_NAME>_codebook.json()?, accessed based on filename,
    #  and inserted here
    # todo: check git status first to ensure clean? maybe doesn't matter since we can just add by filename
    path = os.path.join(path_root, dataset_path)
    # noinspection PyBroadException
    try:
        df = pd.read_csv(path, dtype={'id': np.int32, 'last_name': str, 'first_name': str}).fillna('')
        for index, field_values in row_index_data_map.items():
            for field, value in field_values.items():
                df.at[index, field] = value
        df.to_csv(path, index=False)
    except BaseException as err:
        result = 'failure'
        details = str(err)

    # Push commit
    # todo?: Correct git status after change should show something like this near end: `modified: FILENAME`
    relative_path = os.path.join('datasets', dataset_path)
    # todo: Want to see result as string? only getting int: 1 / 0
    #  ...answer: it's being printed to stderr and stdout. I remember there's some way to pipe and capture if needed
    # TODO: What if the update resulted in no changes? e.g. changed values were same?
    git_add_result = sp_call(f'git add {relative_path}'.split(), cwd=cset_dir)
    if git_add_result != 0:
        result = 'failure'
        details = f'Error: Git add: {dataset_path}'
    git_commit_result = sp_call(['git', 'commit', '-m', f'Updated by server: {relative_path}'], cwd=cset_dir)
    if git_commit_result != 0:
        result = 'failure'
        details = f'Error: Git commit: {dataset_path}'
    git_push_result = sp_call('git push origin HEAD:main'.split(), cwd=cset_dir)
    if git_push_result != 0:
        result = 'failure'
        details = f'Error: Git push: {dataset_path}'

    return {'result': result, 'details': details}


# TODO: Maybe change to `id` instead of row index
@APP.put("/datasets/csets")
def put_csets_update(d: CsetsGitUpdate = None) -> Dict:
    """HTTP PUT wrapper for csets_update()"""
    return csets_git_update(d.dataset_path, d.row_index_data_map)


@APP.put("/datasets/vocab")
def vocab_update():
    """Update vocab dataset"""
    pass


def pdump(o):
    print(json.dumps(o, indent=2))


def run(port: int = 8000):
    """Run app"""
    uvicorn.run(APP, host='0.0.0.0', port=port)


if __name__ == '__main__':
    run()
