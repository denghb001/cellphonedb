import os
import pandas as pd
import numpy as np

from cellcommdb.api import current_dir
from cellcommdb.extensions import db
from cellcommdb.models import Multidata, Protein


def load(complex_file=None):
    if not complex_file:
        complex_file = os.path.join(current_dir, 'data', 'complex.csv')

    existing_complexes = db.session.query(Multidata.uniprot).all()
    existing_complexes = [c[0] for c in existing_complexes]
    proteins = db.session.query(Multidata.uniprot, Multidata.id).join(Protein).all()
    proteins = {p[0]: p[1] for p in proteins}
    # Read in complexes
    complex_df = pd.read_csv(complex_file, quotechar='"', na_values="-")
    complex_df.dropna(axis=1, inplace=True, how='all')

    # Get complex composition info
    complete_indices = []
    complex_map = {}
    for index, row in complex_df.iterrows():
        missing = False
        protein_id_list = []
        for protein in ['protein_1_id', 'protein_2_id',
                        'protein_3_id', 'protein_4_id']:
            if not pd.isnull(row[protein]):
                protein_id = proteins.get(row[protein])
                if protein_id is None:
                    missing = True
                else:
                    protein_id_list.append(protein_id)
        if not missing:
            complex_map[row['uniprot']] = protein_id_list
            complete_indices.append(index)

    # Insert complexes
    if not complex_df.empty:
        # Remove unwanted columns
        removal_columns = list(filter(
            lambda x: 'protein_' in x or 'Name_' in x or 'Unnamed' in x,
            complex_df.columns))
        # removal_columns += ['comments']
        complex_df.drop(removal_columns, axis=1, inplace=True)

        # Remove rows with missing complexes
        complex_df = complex_df.iloc[complete_indices, :]

        # Convert ints to bool
        bools = ['receptor', 'receptor_highlight', 'adhesion', 'other',
                 'transporter', 'secreted_highlight']
        complex_df[bools] = complex_df[bools].astype(bool)

        # Drop existing complexes
        complex_df = complex_df[complex_df['uniprot'].apply(
            lambda x: x not in existing_complexes)]

        complex_df.to_sql(name='multidata', if_exists='append',
                          con=db.engine, index=False)

    # Now find id's of new complex rows
    new_complexes = db.session.query(Multidata.uniprot, Multidata.id).all()
    new_complexes = {c[0]: c[1] for c in new_complexes}

    # Build set of complexes
    complex_set = []
    complex_table = []
    for complex_name in complex_map:
        complex_id = new_complexes[complex_name]
        for protein_id in complex_map[complex_name]:
            complex_set.append((complex_id, protein_id))
        complex_table.append(complex_id)

    # Insert complex composition
    complex_set_df = pd.DataFrame(complex_set,
                                  columns=['complex_multidata_id', 'protein_multidata_id'])

    complex_table_df = pd.DataFrame(complex_table, columns=['complex_multidata_id'])

    complex_set_df.to_sql(
        name='complex_composition', if_exists='append',
        con=db.engine, index=False)

    complex_table_df.to_sql(
        name='complex', if_exists='append',
        con=db.engine, index=False)