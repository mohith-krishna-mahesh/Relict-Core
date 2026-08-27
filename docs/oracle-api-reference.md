
# ENSEMBL REST API

```
EnsemblClient
│
├── Core Ensembl
│   │
│   ├── Gene Identity / Lookup
│   │   │
│   │   ├── GET /lookup/symbol/:species/:symbol
│   │   │   API:
│   │   │   https://rest.ensembl.org/lookup/symbol/:species/:symbol
│   │   │   Docs:
│   │   │   https://rest.ensembl.org/documentation/info/symbol_lookup
│   │   │
│   │   │   Purpose:
│   │   │   Resolve a gene symbol within a species to its Ensembl
│   │   │   gene/feature record.
│   │   │
│   │   │   Relict use:
│   │   │   Convert gene names into canonical Ensembl identifiers.
│   │   │
│   │   │
│   │   └── GET /lookup/id/:id
│   │       API:
│   │       https://rest.ensembl.org/lookup/id/:id
│   │       Docs:
│   │       https://rest.ensembl.org/documentation/info/lookup
│   │
│   │       Purpose:
│   │       Resolve an Ensembl stable identifier to its feature record.
│   │
│   │       Relict use:
│   │       Validate and enrich resolved Ensembl IDs.
│   │
│   │
│   ├── Cross-References
│   │   │
│   │   ├── GET /xrefs/symbol/:species/:symbol
│   │   │   API:
│   │   │   https://rest.ensembl.org/xrefs/symbol/:species/:symbol
│   │   │   Docs:
│   │   │   https://rest.ensembl.org/documentation/info/xref_external
│   │   │
│   │   │   Purpose:
│   │   │   Retrieve external database cross-references for a gene.
│   │   │
│   │   │   Relict use:
│   │   │   Map Ensembl identifiers to NCBI, UniProt, STRING and
│   │   │   other database identifiers.
│   │   │
│   │   │
│   │   └── GET /xrefs/id/:id
│   │       API:
│   │       https://rest.ensembl.org/xrefs/id/:id
│   │       Docs:
│   │       https://rest.ensembl.org/documentation/info/xref_id
│   │
│   │       Purpose:
│   │       Retrieve external cross-references for an Ensembl ID.
│   │
│   │       Relict use:
│   │       Identifier normalization and cross-database linking.
│   │
│   │
│   ├── Phenotype
│   │   │
│   │   ├── GET /phenotype/gene/:species/:gene
│   │   │   API:
│   │   │   https://rest.ensembl.org/phenotype/gene/:species/:gene
│   │   │   Docs:
│   │   │   https://rest.ensembl.org/documentation/info/phenotype_gene
│   │   │
│   │   │   Purpose:
│   │   │   Retrieve phenotype/trait associations for a gene.
│   │   │
│   │   │   Relict use:
│   │   │   Build gene → phenotype/trait evidence relationships.
│   │   │
│   │   │
│   │   └── GET /phenotype/term/:species/:term
│   │       API:
│   │       https://rest.ensembl.org/phenotype/term/:species/:term
│   │       Docs:
│   │       https://rest.ensembl.org/documentation/info/phenotype_term
│   │
│   │       Purpose:
│   │       Retrieve genomic features associated with a phenotype term.
│   │
│   │       Relict use:
│   │       Resolve phenotypes into candidate genomic features.
│   │
│   │
│   ├── Sequence
│   │   │
│   │   ├── GET /sequence/id/:id
│   │   │   API:
│   │   │   https://rest.ensembl.org/sequence/id/:id
│   │   │   Docs:
│   │   │   https://rest.ensembl.org/documentation/info/sequence_id
│   │   │
│   │   │   Purpose:
│   │   │   Retrieve sequence associated with an Ensembl feature.
│   │   │
│   │   │   Relict use:
│   │   │   Supply sequences to downstream sequence analysis.
│   │   │
│   │   │
│   │   └── GET /sequence/region/:species/:region
│   │       API:
│   │       https://rest.ensembl.org/sequence/region/:species/:region
│   │       Docs:
│   │       https://rest.ensembl.org/documentation/info/sequence_region
│   │
│   │       Purpose:
│   │       Retrieve genomic sequence for a region.
│   │
│   │       Relict use:
│   │       Retrieve sequence surrounding genomic coordinates.
│   │
│   │
│   ├── Species
│   │   │
│   │   └── GET /info/species
│   │       API:
│   │       https://rest.ensembl.org/info/species
│   │       Docs:
│   │       https://rest.ensembl.org/documentation/info/species
│   │
│   │       Purpose:
│   │       Retrieve species supported by the Ensembl instance.
│   │
│   │       Relict use:
│   │       Validate species and Ensembl naming.
│   │
│   │
│   ├── Assembly
│   │   │
│   │   └── GET /info/assembly/:species
│   │       API:
│   │       https://rest.ensembl.org/info/assembly/:species
│   │       Docs:
│   │       https://rest.ensembl.org/documentation/info/assembly_info
│   │
│   │       Purpose:
│   │       Retrieve genome assembly information.
│   │
│   │       Relict use:
│   │       Establish assembly context for genomic coordinates.
│   │
│   │
│   └── Taxonomy
│       │
│       ├── GET /taxonomy/id/:id
│       │   API:
│       │   https://rest.ensembl.org/taxonomy/id/:id
│       │   Docs:
│       │   https://rest.ensembl.org/documentation/info/taxonomy_id
│       │
│       │   Purpose:
│       │   Retrieve taxonomy information by identifier.
│       │
│       │
│       ├── GET /taxonomy/name/:name
│       │   API:
│       │   https://rest.ensembl.org/taxonomy/name/:name
│       │   Docs:
│       │   https://rest.ensembl.org/documentation/info/taxonomy_name
│       │
│       │   Purpose:
│       │   Resolve a taxonomic name.
│       │
│       │
│       └── GET /taxonomy/classification/:id
│           API:
│           https://rest.ensembl.org/taxonomy/classification/:id
│           Docs:
│           https://rest.ensembl.org/documentation/info/taxonomy_classification
│
│           Purpose:
│           Retrieve the taxonomic hierarchy.
│
│
├── Ensembl Compara
│   │
│   ├── Homology
│   │   │
│   │   ├── GET /homology/symbol/:species/:symbol
│   │   │   API:
│   │   │   https://rest.ensembl.org/homology/symbol/:species/:symbol
│   │   │   Docs:
│   │   │   https://rest.ensembl.org/documentation/info/homology_symbol
│   │   │
│   │   │   Purpose:
│   │   │   Retrieve orthologous/paralogous relationships by symbol.
│   │   │
│   │   │   Relict use:
│   │   │   Cross-species and evolutionary relationship evidence.
│   │   │
│   │   │
│   │   └── GET /homology/id/:species/:id
│   │       API:
│   │       https://rest.ensembl.org/homology/id/:species/:id
│   │       Docs:
│   │       https://rest.ensembl.org/documentation/info/homology_species_gene_id
│   │
│   │       Purpose:
│   │       Retrieve homology from an Ensembl identifier.
│   │
│   │
│   ├── Gene Tree
│   │   │
│   │   ├── GET /genetree/member/symbol/:species/:symbol
│   │   │   API:
│   │   │   https://rest.ensembl.org/genetree/member/symbol/:species/:symbol
│   │   │   Docs:
│   │   │   https://rest.ensembl.org/documentation/info/genetree_member_symbol
│   │   │
│   │   │   Purpose:
│   │   │   Retrieve the gene tree containing a gene.
│   │   │
│   │   │   Relict use:
│   │   │   Evolutionary tree context.
│   │   │
│   │   │
│   │   └── GET /genetree/member/id/:species/:id
│   │       API:
│   │       https://rest.ensembl.org/genetree/member/id/:species/:id
│   │       Docs:
│   │       https://rest.ensembl.org/documentation/info/genetree_species_member_id
│   │
│   │       Purpose:
│   │       Retrieve a gene tree from an Ensembl ID.
│   │
│   │
│   └── Compara Configuration
│       │
│       ├── GET /info/compara/methods
│       │   API:
│       │   https://rest.ensembl.org/info/compara/methods
│       │   Docs:
│       │   https://rest.ensembl.org/documentation/info/compara_methods
│       │
│       │   Purpose:
│       │   Retrieve available comparative-genomics methods.
│       │
│       │
│       └── GET /info/compara/species_sets/:method
│           API:
│           https://rest.ensembl.org/info/compara/species_sets/:method
│           Docs:
│           https://rest.ensembl.org/documentation/info/compara_species_sets
│
│           Purpose:
│           Retrieve species sets available for a Compara method.
│
│
└── Ensembl Variation
    │
    ├── Variant Retrieval
    │   │
    │   ├── GET /variation/:species/:id
    │   │   API:
    │   │   https://rest.ensembl.org/variation/:species/:id
    │   │   Docs:
    │   │   https://rest.ensembl.org/documentation/info/variation_id
    │   │
    │   │   Purpose:
    │   │   Retrieve variation features including optional genotype,
    │   │   phenotype and population data.
    │   │
    │   │   Relict use:
    │   │   Variant identity, population and phenotype evidence.
    │   │
    │   │
    │   └── POST /variation/:species
    │       API:
    │       https://rest.ensembl.org/variation/:species
    │       Docs:
    │       https://rest.ensembl.org/documentation/info/variation_post
    │
    │       Purpose:
    │       Batch retrieval of variant information.
    │
    │       Relict use:
    │       Efficient variant retrieval for multiple identifiers.
    │
    │
    ├── Variant Recoder
    │   │
    │   ├── GET /variant_recoder/:species/:id
    │   │   API:
    │   │   https://rest.ensembl.org/variant_recoder/:species/:id
    │   │   Docs:
    │   │   https://rest.ensembl.org/documentation/info/variant_recoder
    │   │
    │   │   Purpose:
    │   │   Convert variant identifiers between representations.
    │   │
    │   │   Relict use:
    │   │   Normalize rsIDs, HGVS and genomic representations.
    │   │
    │   │
    │   └── POST /variant_recoder/:species
    │       API:
    │       https://rest.ensembl.org/variant_recoder/:species
    │       Docs:
    │       https://rest.ensembl.org/documentation/info/variant_recoder_post
    │
    │       Purpose:
    │       Batch variant normalization/recoding.
    │
    │
    ├── Variation Sources
    │   │
    │   └── GET /info/variation/:species
    │       API:
    │       https://rest.ensembl.org/info/variation/:species
    │       Docs:
    │       https://rest.ensembl.org/documentation/info/variation
    │
    │       Purpose:
    │       List variation sources used by Ensembl.
    │
    │       Supported filters include:
    │       ├── dbSNP
    │       ├── ClinVar
    │       ├── OMIM
    │       ├── UniProt
    │       └── HGMD
    │
    │
    └── Variant Effect Predictor (VEP)
        │
        ├── By Variant ID
        │   │
        │   ├── GET /vep/:species/id/:id
        │   │   API:
        │   │   https://rest.ensembl.org/vep/:species/id/:id
        │   │   Docs:
        │   │   https://rest.ensembl.org/documentation/info/vep_id_get
        │   │
        │   │   Purpose:
        │   │   Predict/annotate consequences of a variant identifier.
        │   │
        │   │   Relict use:
        │   │   Variant → gene → transcript → molecular consequence.
        │   │
        │   │
        │   │   Supports:
        │   │   ├── dbSNP IDs
        │   │   ├── COSMIC IDs
        │   │   ├── HGMD IDs
        │   │   └── structural variant identifiers
        │   │
        │   └── POST /vep/:species/id
        │       API:
        │       https://rest.ensembl.org/vep/:species/id
        │       Docs:
        │       https://rest.ensembl.org/documentation/info/vep_id_post
        │
        │       Purpose:
        │       Batch VEP annotation for variant identifiers.
        │
        │
        ├── By Genomic Region
        │   │
        │   ├── GET /vep/:species/region/:region
        │   │   API:
        │   │   https://rest.ensembl.org/vep/:species/region/:region
        │   │   Docs:
        │   │   https://rest.ensembl.org/documentation/info/vep_region_get
        │   │
        │   │   Purpose:
        │   │   Annotate variants supplied as genomic coordinates.
        │   │
        │   │
        │   └── POST /vep/:species/region
        │       API:
        │       https://rest.ensembl.org/vep/:species/region
        │       Docs:
        │       https://rest.ensembl.org/documentation/info/vep_region_post
        │
        │       Purpose:
        │       Batch annotation of variants specified by genomic
        │       coordinates.
        │
        │
        └── By HGVS
            └── GET /vep/:species/hgvs/:hgvs_notation
                API:
                https://rest.ensembl.org/vep/:species/hgvs/:hgvs_notation
                Docs:
                https://rest.ensembl.org/documentation/info/vep_hgvs_get

                Purpose:
                Annotate variants represented in HGVS notation.

                Relict use:
                Interpret user/researcher-supplied HGVS variants.
```


# STRING REST API

```

STRINGClient
│
├── Identifier Mapping
│   │
│   └── POST /api/json/get_string_ids
│       API:
│       https://version-12-0.string-db.org/api/json/get_string_ids
│
│       Purpose:
│       Map external identifiers or protein/gene names to STRING
│       protein identifiers.
│
│       Main inputs:
│       ├── identifiers
│       ├── species
│       └── caller_identity
│
│       Relict use:
│       Identifier normalization before querying STRING relationships.
│
│
├── Interaction Network
│   │
│   └── POST /api/json/network
│       API:
│       https://version-12-0.string-db.org/api/json/network
│
│       Purpose:
│       Retrieve the functional association network around a set
│       of proteins.
│
│       Relict use:
│       Primary STRING source for Evidence Graph interaction edges.
│
│
├── Interaction Partners
│   │
│   └── POST /api/json/interaction_partners
│       API:
│       https://version-12-0.string-db.org/api/json/interaction_partners
│
│       Purpose:
│       Retrieve proteins interacting/associated with supplied
│       proteins.
│
│       Relict use:
│       Expand the Evidence Graph around candidate genes/proteins.
│
│
├── Protein Homology
│   │
│   ├── POST /api/json/homology
│   │   API:
│   │   https://version-12-0.string-db.org/api/json/homology
│   │
│   │   Purpose:
│   │   Retrieve homologous proteins.
│   │
│   │   Relict use:
│   │   Additional evolutionary relationship evidence.
│   │
│   └── POST /api/json/homology_best
│       API:
│       https://version-12-0.string-db.org/api/json/homology_best
│
│       Purpose:
│       Retrieve the best homologous relationships.
│
│       Relict use:
│       Higher-specificity homology evidence when expanding
│       candidate relationships.
│
│
├── Functional Analysis
│   │
│   ├── POST /api/json/enrichment
│   │   API:
│   │   https://version-12-0.string-db.org/api/json/enrichment
│   │
│   │   Purpose:
│   │   Perform functional enrichment on an input protein set.
│   │
│   │   Relict use:
│   │   Identify statistically enriched biological processes,
│   │   pathways, functions, diseases, compartments, domains, etc.
│   │
│   ├── POST /api/json/functional_annotation
│   │   API:
│   │   https://version-12-0.string-db.org/api/json/functional_annotation
│   │
│   │   Purpose:
│   │   Retrieve functional annotations associated with proteins.
│   │
│   │   Relict use:
│   │   Attach functional evidence to candidate genes/proteins.
│   │
│   └── POST /api/json/functional_terms
│       API:
│       https://version-12-0.string-db.org/api/json/functional_terms
│
│       Purpose:
│       Find STRING functional terms matching an identifier or
│       free-text biological concept and retrieve proteins annotated
│       with those terms.
│
│       Main inputs:
│       ├── term_text
│       ├── species
│       └── caller_identity
│
│       Output includes:
│       ├── category
│       ├── term
│       ├── description
│       ├── proteinCount
│       ├── preferredNames
│       └── stringIds
│
│       Relict use:
│       Objective/phenotype concept → functional term → candidate
│       proteins.
│
│
├── Gene Set Interpretation
│   │
│   └── POST /api/json/geneset_description
│       API:
│       https://version-12-0.string-db.org/api/json/geneset_description
│
│       Purpose:
│       Generate short biological descriptions for an input
│       protein/gene set based on enriched functional themes.
│
│       Output:
│       ├── primary_description
│       ├── secondary_description
│       └── tertiary_description
│
│       Relict use:
│       Interpret/summarize a selected gene set after planning.
│       This is supporting interpretation, not primary graph-edge
│       construction.
│
│
├── Network Validation
│   │
│   └── POST /api/json/ppi_enrichment
│       API:
│       https://version-12-0.string-db.org/api/json/ppi_enrichment
│
│       Purpose:
│       Determine whether the supplied protein set has more
│       interactions than expected by chance.
│
│       Relict use:
│       Validate whether a planned/candidate gene set forms a
│       biologically connected network.
│
│
└── Version / Provenance
    │
    └── GET /api/json/version
        API:
        https://version-12-0.string-db.org/api/json/version

        Purpose:
        Identify the STRING database version being queried.

        Relict use:
        Store database-version provenance with retrieved evidence.

```


# KEGG REST API

```
KEGGClient
│
├── Database Information
│   │
│   └── GET /info/<database>
│       API:
│       https://rest.kegg.jp/info/<database>
│
│       Supported database classes:
│       ├── pathway
│       ├── brite
│       ├── module
│       ├── ko
│       ├── genes / <org>
│       ├── genome
│       ├── vtax
│       ├── vgenome
│       ├── compound
│       ├── glycan
│       ├── reaction
│       ├── rclass
│       ├── rmodule
│       ├── enzyme
│       ├── network
│       ├── ntmap
│       ├── variant
│       ├── disease
│       ├── drug
│       └── dgroup
│
│       Purpose:
│       Retrieve KEGG release information, database statistics,
│       and linked-database information.
│
│       Relict use:
│       Database/release validation and provenance.
│
│
├── Entry Listing
│   │
│   ├── GET /list/<database>
│   │   API:
│   │   https://rest.kegg.jp/list/<database>
│   │
│   │   Purpose:
│   │   Retrieve identifiers and associated names for entries
│   │   in a KEGG database.
│   │
│   │
│   ├── GET /list/pathway/<org>
│   │   API:
│   │   https://rest.kegg.jp/list/pathway/<org>
│   │
│   │   Purpose:
│   │   Retrieve organism-specific pathways.
│   │
│   │   Relict use:
│   │   Discover pathways available for the project species.
│   │
│   │
│   ├── GET /list/brite/<option>
│   │   API:
│   │   https://rest.kegg.jp/list/brite/<option>
│   │
│   │   Options:
│   │   ├── br
│   │   ├── jp
│   │   ├── ko
│   │   └── <org>
│   │
│   │   Purpose:
│   │   Retrieve BRITE hierarchy entries.
│   │
│   │
│   ├── GET /list/genome/<option>
│   │   API:
│   │   https://rest.kegg.jp/list/genome/<option>
│   │
│   │   Options:
│   │   ├── group name
│   │   └── taxonomy rank ID
│   │
│   │   Purpose:
│   │   Retrieve KEGG genome/organism entries by group or
│   │   taxonomic rank.
│   │
│   │
│   ├── GET /list/<dbentries>
│   │   API:
│   │   https://rest.kegg.jp/list/<dbentries>
│   │
│   │   Limit:
│   │   Maximum 10 identifiers.
│   │
│   │   Purpose:
│   │   Retrieve names/definitions for a selected set of
│   │   database entries.
│   │
│   │
│   └── GET /list/organism
│       API:
│       https://rest.kegg.jp/list/organism
│
│       Purpose:
│       Retrieve KEGG organisms and their organism codes.
│
│       Relict use:
│       Resolve project species to a KEGG organism code.
│
│
├── Entry Search
│   │
│   ├── GET /find/<database>/<query>
│   │   API:
│   │   https://rest.kegg.jp/find/<database>/<query>
│   │
│   │   Purpose:
│   │   Search KEGG entries by identifier/name/keyword.
│   │
│   │   Relict use:
│   │   Resolve biological concepts, gene names, pathways,
│   │   diseases, modules, etc. into KEGG entries.
│   │
│   │
│   ├── GET /find/<database>/<query>/formula
│   │   API:
│   │   https://rest.kegg.jp/find/<database>/<query>/formula
│   │
│   │   Purpose:
│   │   Partial chemical-formula matching.
│   │
│   │
│   ├── GET /find/<database>/<query>/exact_mass
│   │   API:
│   │   https://rest.kegg.jp/find/<database>/<query>/exact_mass
│   │
│   │   Purpose:
│   │   Search compounds/drugs by exact mass.
│   │
│   │
│   ├── GET /find/<database>/<query>/mol_weight
│   │   API:
│   │   https://rest.kegg.jp/find/<database>/<query>/mol_weight
│   │
│   │   Purpose:
│   │   Search compounds/drugs by molecular weight.
│   │
│   │
│   └── GET /find/<database>/<query>/nop
│       API:
│       https://rest.kegg.jp/find/<database>/<query>/nop
│
│       Purpose:
│       Disable KEGG's keyword-processing behavior for
│       searches where literal matching is desired.
│
│       Relict note:
│       Chemical-search variants are probably outside the initial
│       gene/pathway planning scope, but they belong in the
│       underlying KEGG client if full API coverage is desired.
│
│
├── Entry Retrieval
│   │
│   └── GET /get/<dbentries>[/<option>]
│       API:
│       https://rest.kegg.jp/get/<dbentries>
│
│       Input limit:
│       Maximum 10 entries for normal retrieval.
│
│       Default:
│       KEGG flat-file database format.
│
│       Options:
│       │
│       ├── /aaseq
│       │   Retrieve amino-acid sequence from gene entries.
│       │
│       ├── /ntseq
│       │   Retrieve nucleotide sequence from gene entries.
│       │
│       ├── /mol
│       │   Retrieve molecular structure representation.
│       │
│       ├── /kcf
│       │   Retrieve KCF chemical structure representation.
│       │
│       ├── /image
│       │   Retrieve image representation of supported
│       │   compound/glycan/drug/pathway entries.
│       │
│       ├── /conf
│       │   Retrieve pathway map configuration.
│       │
│       ├── /kgml
│       │   Retrieve pathway KGML representation.
│       │
│       └── /json
│           Retrieve JSON representation where supported.
│
│       Relict use:
│       Retrieve authoritative KEGG records after entry
│       resolution.
│
│       Particularly relevant:
│       ├── pathway
│       ├── ko
│       ├── module
│       ├── genes
│       ├── reaction
│       ├── enzyme
│       └── network
│
│       KGML is particularly useful when Relict needs the
│       structured pathway graph rather than only the textual
│       pathway record.
│
│
├── Identifier Conversion
│   │
│   ├── GET /conv/<target_db>/<source_db>
│   │   API:
│   │   https://rest.kegg.jp/conv/<target_db>/<source_db>
│   │
│   │   Purpose:
│   │   Perform database-wide identifier conversion.
│   │
│   │   Gene mappings:
│   │   ├── KEGG organism ↔ NCBI GeneID
│   │   ├── KEGG organism ↔ NCBI ProteinID
│   │   └── KEGG organism ↔ UniProt
│   │
│   │   Chemical mappings:
│   │   ├── compound/glycan/drug ↔ PubChem
│   │   └── compound/glycan/drug ↔ ChEBI
│   │
│   │
│   └── GET /conv/<target_db>/<dbentries>
│       API:
│       https://rest.kegg.jp/conv/<target_db>/<dbentries>
│
│       Purpose:
│       Convert selected identifiers rather than an entire
│       database.
│
│       Special case:
│       "genes" may be used when the organism code is unknown.
│
│       Relict use:
│       Identifier normalization between Ensembl/NCBI/UniProt
│       and KEGG.
│
│
├── Cross-Database Relationships
│   │
│   ├── GET /link/<target_db>/<source_db>
│   │   API:
│   │   https://rest.kegg.jp/link/<target_db>/<source_db>
│   │
│   │   Purpose:
│   │   Retrieve all cross-references between two databases.
│   │
│   │
│   ├── GET /link/<target_db>/<dbentries>
│   │   API:
│   │   https://rest.kegg.jp/link/<target_db>/<dbentries>
│   │
│   │   Purpose:
│   │   Retrieve relationships for selected entries.
│   │
│   │   Core Relict relationships:
│   │   ├── gene → pathway
│   │   ├── pathway → gene
│   │   ├── gene → KO
│   │   ├── pathway → KO
│   │   ├── pathway → reaction
│   │   ├── pathway → compound
│   │   └── other KEGG cross-references
│   │
│   │
│   └── Taxonomic link options
│       ├── species
│       ├── genus
│       ├── family
│       ├── order
│       ├── class
│       └── phylum
│
│       Purpose:
│       Filter or organize genome/taxonomy relationships
│       at different taxonomic levels.
│
│
├── External Database Links
│   │
│   └── /link/<target_db>/<source_db>
│
│       Supported external databases include:
│       ├── pubmed
│       ├── taxonomy
│       ├── atc
│       ├── jtc
│       ├── ndc
│       └── yk
│
│       Relict use:
│       Cross-reference KEGG evidence with external identifiers
│       and literature/taxonomy/drug classification data where
│       required.
│
│
├── RDF Link Output
│   │
│   └── /link/<target_db>/<dbentries>/<option>
│
│       Supported scope:
│       ├── drug
│       ├── atc
│       └── jtc
│
│       Options:
│       ├── turtle
│       └── n-triple
│
│       Purpose:
│       Retrieve selected drug/classification relationships
│       as RDF.
│
│       Relict use:
│       Not required for the initial gene/pathway Evidence Graph.
│
│
└── Drug–Drug Interaction
    │
    ├── GET /ddi/<dbentry>
    │   API:
    │   https://rest.kegg.jp/ddi/<dbentry>
    │
    └── GET /ddi/<dbentries>
        API:
        https://rest.kegg.jp/ddi/<dbentries>

        Supported databases:
        ├── drug
        ├── ndc
        └── yj

        Purpose:
        Retrieve known adverse drug-drug interactions.

        Relict use:
        OUTSIDE INITIAL SCOPE.
```


# NCBI REST API


```
NCBIClient
│
├── Entrez E-Utilities
│   │
│   ├── Database Information
│   │   └── EInfo
│   │       GET/POST /entrez/eutils/einfo.fcgi
│   │       API:
│   │       https://eutils.ncbi.nlm.nih.gov/entrez/eutils/einfo.fcgi
│   │       Docs:
│   │       https://www.ncbi.nlm.nih.gov/books/n/helpeutils/chapter4/#chapter4.EInfo
│   │
│   │       Purpose:
│   │       Retrieve Entrez database metadata, available fields,
│   │       search capabilities and record statistics.
│   │
│   │       Relict use:
│   │       Database discovery, field validation and provenance.
│   │
│   │
│   ├── Search
│   │   └── ESearch
│   │       GET/POST /entrez/eutils/esearch.fcgi
│   │       API:
│   │       https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi
│   │       Docs:
│   │       https://www.ncbi.nlm.nih.gov/books/n/helpeutils/chapter4/#chapter4.ESearch
│   │
│   │       Purpose:
│   │       Search an Entrez database and return matching UIDs.
│   │
│   │       Relict use:
│   │       Resolve genes, proteins, variants, phenotypes,
│   │       literature and other biological concepts into
│   │       NCBI records.
│   │
│   │
│   ├── UID History
│   │   └── EPost
│   │       GET/POST /entrez/eutils/epost.fcgi
│   │       API:
│   │       https://eutils.ncbi.nlm.nih.gov/entrez/eutils/epost.fcgi
│   │       Docs:
│   │       https://www.ncbi.nlm.nih.gov/books/n/helpeutils/chapter4/#chapter4.EPost
│   │
│   │       Purpose:
│   │       Upload UID sets to the NCBI History server.
│   │
│   │       Relict use:
│   │       Efficient transfer of large intermediate record
│   │       sets between E-Utilities.
│   │
│   │
│   ├── Record Summaries
│   │   └── ESummary
│   │       GET/POST /entrez/eutils/esummary.fcgi
│   │       API:
│   │       https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi
│   │       Docs:
│   │       https://www.ncbi.nlm.nih.gov/books/n/helpeutils/chapter4/#chapter4.ESummary
│   │
│   │       Purpose:
│   │       Retrieve lightweight summaries for Entrez records.
│   │
│   │       Relict use:
│   │       Metadata retrieval and filtering before requesting
│   │       complete records.
│   │
│   │
│   ├── Full Records
│   │   └── EFetch
│   │       GET/POST /entrez/eutils/efetch.fcgi
│   │       API:
│   │       https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi
│   │       Docs:
│   │       https://www.ncbi.nlm.nih.gov/books/n/helpeutils/chapter4/#chapter4.EFetch
│   │
│   │       Purpose:
│   │       Retrieve complete records from Entrez databases.
│   │
│   │       Relict use:
│   │       Retrieve authoritative Gene, Protein, Nucleotide,
│   │       PubMed, PMC, ClinVar and other NCBI records.
│   │
│   │
│   ├── Cross-Database Links
│   │   └── ELink
│   │       GET/POST /entrez/eutils/elink.fcgi
│   │       API:
│   │       https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi
│   │       Docs:
│   │       https://www.ncbi.nlm.nih.gov/books/n/helpeutils/chapter4/#chapter4.ELink
│   │
│   │       Purpose:
│   │       Retrieve records linked to records in another
│   │       Entrez database.
│   │
│   │       Relict use:
│   │       Construct cross-database evidence relationships.
│   │
│   │
│   ├── Global Search
│   │   └── EGQuery
│   │       GET/POST /entrez/eutils/egquery.fcgi
│   │       API:
│   │       https://eutils.ncbi.nlm.nih.gov/entrez/eutils/egquery.fcgi
│   │       Docs:
│   │       https://www.ncbi.nlm.nih.gov/books/n/helpeutils/chapter4/#chapter4.EGQuery
│   │
│   │       Purpose:
│   │       Search across Entrez databases and return
│   │       database-level hit counts.
│   │
│   │       Relict use:
│   │       Broad retrieval discovery and database selection.
│   │
│   │
│   ├── Spelling
│   │   └── ESpell
│   │       GET/POST /entrez/eutils/espell.fcgi
│   │       API:
│   │       https://eutils.ncbi.nlm.nih.gov/entrez/eutils/espell.fcgi
│   │       Docs:
│   │       https://www.ncbi.nlm.nih.gov/books/n/helpeutils/chapter4/#chapter4.ESpell
│   │
│   │       Purpose:
│   │       Return spelling suggestions for Entrez search terms.
│   │
│   │       Relict use:
│   │       Search-query correction and normalization.
│   │
│   │
│   └── Citation Matching
│       └── ECitMatch
│           GET/POST /entrez/eutils/ecitmatch.cgi
│           API:
│           https://eutils.ncbi.nlm.nih.gov/entrez/eutils/ecitmatch.cgi
│           Docs:
│           https://www.ncbi.nlm.nih.gov/books/n/helpeutils/chapter4/#chapter4.ECitMatch
│
│           Purpose:
│           Match citation strings to PubMed records.
│
│           Relict use:
│           Resolve bibliographic references to PubMed IDs.
│
│
├── ClinVar
│   │
│   └── Entrez Database: clinvar
│       │
│       ├── ESearch
│       │   GET/POST /entrez/eutils/esearch.fcgi
│       │   API:
│       │   https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi
│       │   Docs:
│       │   https://www.ncbi.nlm.nih.gov/books/n/helpeutils/chapter4/#chapter4.ESearch
│       │
│       │   Database:
│       │   clinvar
│       │
│       │   Purpose:
│       │   Search ClinVar records using the Entrez query language.
│       │
│       │   Relict use:
│       │   ├── gene → clinically reported variants
│       │   ├── variant → ClinVar records
│       │   ├── disease → associated variants
│       │   ├── clinical-significance searches
│       │   └── variant discovery
│       │
│       │
│       ├── ESummary
│       │   GET/POST /entrez/eutils/esummary.fcgi
│       │   API:
│       │   https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi
│       │   Docs:
│       │   https://www.ncbi.nlm.nih.gov/books/n/helpeutils/chapter4/#chapter4.ESummary
│       │
│       │   Database:
│       │   clinvar
│       │
│       │   Purpose:
│       │   Retrieve lightweight structured summaries of ClinVar
│       │   records identified by their UIDs.
│       │
│       │   Relict use:
│       │   ├── variant metadata
│       │   ├── ClinVar identifiers
│       │   ├── clinical significance
│       │   ├── review status
│       │   └── preliminary record filtering
│       │
│       │
│       ├── EFetch
│       │   GET/POST /entrez/eutils/efetch.fcgi
│       │   API:
│       │   https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi
│       │   Docs:
│       │   https://www.ncbi.nlm.nih.gov/books/n/helpeutils/chapter4/#chapter4.EFetch
│       │
│       │   Database:
│       │   clinvar
│       │
│       │   Purpose:
│       │   Retrieve complete ClinVar records.
│       │
│       │   Relict use:
│       │   ├── variant annotations
│       │   ├── clinical significance
│       │   ├── disease/condition associations
│       │   ├── review status
│       │   ├── submitter information
│       │   ├── evidence/provenance
│       │   ├── genomic coordinates
│       │   └── HGVS representations
│       │
│       │
│       └── ELink
│           GET/POST /entrez/eutils/elink.fcgi
│           API:
│           https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi
│           Docs:
│           https://www.ncbi.nlm.nih.gov/books/n/helpeutils/chapter4/#chapter4.ELink
│
│           Database:
│           clinvar
│
│           Purpose:
│           Retrieve relationships between ClinVar records and
│           records in other NCBI databases.
│
│           Relict use:
│           ├── ClinVar ↔ PubMed
│           ├── ClinVar ↔ Gene
│           ├── ClinVar ↔ MedGen
│           └── cross-database evidence relationships
│
│
├── dbSNP
│   │
│   └── Entrez Database: snp
│       │
│       ├── ESearch
│       │   GET/POST /entrez/eutils/esearch.fcgi
│       │   API:
│       │   https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi
│       │   Docs:
│       │   https://www.ncbi.nlm.nih.gov/books/n/helpeutils/chapter4/#chapter4.ESearch
│       │
│       │   Database:
│       │   snp
│       │
│       │   Purpose:
│       │   Search dbSNP records using rsIDs, genomic coordinates,
│       │   genes and supported Entrez search fields.
│       │
│       │   Relict use:
│       │   ├── variant discovery
│       │   ├── rsID resolution
│       │   ├── gene → variant retrieval
│       │   └── variant-set retrieval
│       │
│       │
│       ├── ESummary
│       │   GET/POST /entrez/eutils/esummary.fcgi
│       │   API:
│       │   https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi
│       │   Docs:
│       │   https://www.ncbi.nlm.nih.gov/books/n/helpeutils/chapter4/#chapter4.ESummary
│       │
│       │   Database:
│       │   snp
│       │
│       │   Purpose:
│       │   Retrieve lightweight structured summaries for
│       │   dbSNP records identified by their UIDs.
│       │
│       │   Relict use:
│       │   ├── rsID metadata
│       │   ├── variant identifiers
│       │   ├── allele information
│       │   ├── basic variant information
│       │   └── preliminary record filtering
│       │
│       │
│       ├── EFetch
│       │   GET/POST /entrez/eutils/efetch.fcgi
│       │   API:
│       │   https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi
│       │   Docs:
│       │   https://www.ncbi.nlm.nih.gov/books/n/helpeutils/chapter4/#chapter4.EFetch
│       │
│       │   Database:
│       │   snp
│       │
│       │   Purpose:
│       │   Retrieve complete dbSNP records.
│       │
│       │   Relict use:
│       │   ├── variant identifiers
│       │   ├── allele information
│       │   ├── genomic placements
│       │   ├── variant annotations
│       │   ├── frequency/population information where available
│       │   ├── gene relationships
│       │   └── dbSNP provenance
│       │
│       │
│       └── ELink
│           GET/POST /entrez/eutils/elink.fcgi
│           API:
│           https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi
│           Docs:
│           https://www.ncbi.nlm.nih.gov/books/n/helpeutils/chapter4/#chapter4.ELink
│
│           Database:
│           snp
│
│           Purpose:
│           Retrieve relationships between dbSNP records and
│           records in other NCBI databases.
│
│           Relict use:
│           ├── dbSNP ↔ Gene
│           ├── dbSNP ↔ ClinVar
│           ├── dbSNP ↔ PubMed
│           └── other cross-database evidence relationships
│
│
├── NCBI Datasets v2
│   │
│   ├── Base API
│   │   https://api.ncbi.nlm.nih.gov/datasets/v2/
│   │
│   ├── Documentation
│   │   https://www.ncbi.nlm.nih.gov/datasets/docs/v2/api/rest-api/
│   │
│   ├── OpenAPI Specification
│   │   https://www.ncbi.nlm.nih.gov/datasets/docs/v2/openapi3/openapi3.docs.yaml
│   │
│   ├── Gene
│   │   ├── GET /gene/id/{gene_ids}/dataset_report
│   │   ├── GET /gene/symbol/{symbols}/taxon/{taxon}/dataset_report
│   │   ├── GET /gene/accession/{accessions}/dataset_report
│   │   ├── GET /gene/taxon/{taxon}/dataset_report
│   │   └── GET /gene/locus_tag/{locus_tags}/taxon/{taxon}/dataset_report
│   │
│   │       Purpose:
│   │       Retrieve structured NCBI Gene dataset reports.
│   │
│   │       Relict use:
│   │       Gene metadata, annotations, transcripts, proteins
│   │       and associated sequence information.
│   │
│   │
│   ├── Genome
│   │   ├── Genome dataset/report endpoints
│   │   └── Genome download endpoints
│   │
│   │       Purpose:
│   │       Retrieve structured genome and assembly datasets.
│   │
│   │       Relict use:
│   │       Genome and assembly context where required.
│   │
│   │
│   ├── Taxonomy
│   │   ├── /taxonomy/dataset_report
│   │   └── /taxonomy/taxon/{taxons}/dataset_report
│   │
│   │       Purpose:
│   │       Retrieve structured taxonomy reports.
│   │
│   │       Relict use:
│   │       Species and taxonomic identity/context.
│   │
│   │
│   └── Download Packages
│       ├── Gene packages
│       ├── Genome packages
│       ├── Taxonomy packages
│       └── Other supported datasets
│
│           Purpose:
│           Download cohesive machine-readable NCBI datasets
│           containing metadata and sequence/annotation files.
│
│           Relict use:
│           Large or structured retrieval where a complete
│           dataset package is preferable to individual
│           Entrez records.
│
│
├── BLAST
│   │
│   ├── Base API
│   │   https://blast.ncbi.nlm.nih.gov/Blast.cgi
│   │
│   ├── Documentation
│   │   https://blast.ncbi.nlm.nih.gov/doc/blast-help/urlapi.html
│   │
│   ├── Developer Documentation
│   │   https://blast.ncbi.nlm.nih.gov/doc/blast-help/developerinfo.html
│   │
│   ├── Submit
│   │   └── CMD=Put
│   │
│   │       Purpose:
│   │       Submit a sequence similarity search.
│   │
│   │       Output:
│   │       Request ID (RID).
│   │
│   │       Relict use:
│   │       Sequence similarity/homology evidence when
│   │       required by downstream analysis.
│   │
│   │
│   ├── Status
│   │   └── CMD=Get
│   │
│   │       Purpose:
│   │       Poll a submitted RID until processing completes.
│   │
│   │
│   └── Retrieve Results
│       └── CMD=Get
│
│           Purpose:
│           Retrieve completed BLAST results.
│
│           Supported result representations include:
│           ├── XML2
│           ├── JSON2
│           ├── JSON2_S
│           ├── Text
│           ├── CSV
│           └── other supported formats
│
│           Relict use:
│           Convert sequence-similarity results into
│           downstream homology evidence.
│
│
└── PMC APIs
    │
    ├── OAI-PMH
    │   API:
    │   https://pmc.ncbi.nlm.nih.gov/api/oai/v1/mh/
    │   Docs:
    │   https://pmc.ncbi.nlm.nih.gov/tools/oai/
    │
    │   Purpose:
    │   Retrieve PMC metadata and permitted full text.
    │
    │
    ├── BioC
    │   API:
    │   https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pmcoa.cgi
    │   Docs:
    │   https://www.ncbi.nlm.nih.gov/research/bionlp/APIs/BioC-PMC/
    │
    │   Purpose:
    │   Retrieve Open Access PMC full text in
    │   machine-readable BioC XML/JSON.
    │
    │
    ├── PMC ID Converter
    │   API:
    │   https://pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/
    │   Docs:
    │   https://pmc.ncbi.nlm.nih.gov/tools/id-converter-api/
    │
    │   Purpose:
    │   Convert between PMCID, PMID, DOI and other
    │   article identifiers.
    │
    │
    └── Literature Citation Exporter
        API:
        https://pmc.ncbi.nlm.nih.gov/api/ctxp/

        Docs:
        https://pmc.ncbi.nlm.nih.gov/api/ctxp/

        Purpose:
        Retrieve formatted citations and citation metadata.

```

# UNIPROT REST API

```
UniProtClient
│
├── UniProtKB
│   │
│   ├── GET /uniprotkb/{accession}
│   │   API:
│   │   https://rest.uniprot.org/uniprotkb/{accession}
│   │   Docs:
│   │   https://www.uniprot.org/api-documentation/uniprotkb#operations-UniProtKB-getByAccession
│   │
│   │   Retrieves a single UniProtKB protein entry by accession.
│   │   Returns the protein's structured record, including sequence,
│   │   protein/gene names, organism, function, domains/features,
│   │   interactions, disease information, PTMs, literature,
│   │   cross-references and evidence where available.
│   │
│   └── GET /uniprotkb/search
│       API:
│       https://rest.uniprot.org/uniprotkb/search
│       Docs:
│       https://www.uniprot.org/api-documentation/uniprotkb#operations-UniProtKB-searchCursor
│
│       Searches UniProtKB using UniProt's query syntax and returns
│       paginated matching entries.
│       Supports query expressions, selected fields, sorting,
│       isoform inclusion and pagination.
│
├── UniRef
│   │
│   └── GET /uniref/{id}
│       API:
│       https://rest.uniprot.org/uniref/{id}
│       Docs:
│       https://www.uniprot.org/api-documentation/uniref#operations-UniRef-getById
│
│       Retrieves a UniRef cluster by cluster ID.
│       Provides cluster-level information and the representative
│       sequence/member information useful for sequence clustering
│       and reducing redundant protein sequences.
│
├── UniParc
│   │
│   └── GET /uniparc/{upi}
│       API:
│       https://rest.uniprot.org/uniparc/{upi}
│       Docs:
│       https://www.uniprot.org/api-documentation/uniparc#operations-UniParc-getByUpId
│
│       Retrieves a UniParc sequence record by its UPI.
│       Provides the stable, non-redundant sequence record and
│       provenance/cross-reference information from source databases.
│
├── Proteomes
│   │
│   └── GET /proteomes/{upid}
│       API:
│       https://rest.uniprot.org/proteomes/{upid}
│       Docs:
│       https://www.uniprot.org/api-documentation/proteomes#operations-Proteomes-getByUpId
│
│       Retrieves a UniProt proteome by its UniProt proteome ID.
│       Provides organism/proteome information, genome/assembly
│       information, proteome statistics, completeness information,
│       annotations and related proteome metadata.
│
└── ID Mapping
    │
    ├── POST /idmapping/run
    │   API:
    │   https://rest.uniprot.org/idmapping/run
    │   Docs:
    │   https://www.uniprot.org/api-documentation/idmapping#operations-ID_Mapping_job-submitJob
    │
    │   Submits an asynchronous identifier-mapping job.
    │   Used to translate identifiers between supported biological
    │   databases, such as Ensembl, UniProt, RefSeq and others.
    │
    ├── GET /idmapping/status/{jobId}
    │   API:
    │   https://rest.uniprot.org/idmapping/status/{jobId}
    │   Docs:
    │   https://www.uniprot.org/api-documentation/idmapping#operations-ID_Mapping_job-getStatus
    │
    │   Checks the processing status of a submitted mapping job.
    │
    └── GET /idmapping/results/{jobId}
        API:
        https://rest.uniprot.org/idmapping/results/{jobId}
        Docs:
        https://www.uniprot.org/api-documentation/idmapping#operations-ID_Mapping_results-results

        Retrieves the completed mapping results for a submitted job.
        Depending on the mapping target, results can resolve to
        UniProtKB, UniRef or UniParc records.
```


# REACTOME REST API


```
ReactomeClient
│
├── Content Service
│   │
│   ├── GET /data/query/:stId
│   │   API:
│   │   https://reactome.org/ContentService/data/query/:stId
│   │   Docs:
│   │   https://reactome.org/dev/content-service
│   │
│   │   Retrieves a Reactome object by its stable identifier.
│   │   Used for pathways, reactions/events, biological entities,
│   │   complexes and other Reactome objects.
│   │
│   └── GET /data/event/:stId/participatingPhysicalEntities
│       API:
│       https://reactome.org/ContentService/data/event/:stId/participatingPhysicalEntities
│       Docs:
│       https://reactome.org/dev/content-service
│
│       Retrieves the physical entities participating in a
│       Reactome event/reaction, including proteins, complexes,
│       small molecules and other biological entities.
│
└── Analysis Service
    │
    └── POST /identifiers/
        API:
        https://reactome.org/AnalysisService/identifiers/
        Docs:
        https://reactome.org/dev/analysis

        Submits a list of gene/protein identifiers for Reactome
        pathway analysis.

        Returns pathway-analysis results including matched
        entities, pathways, significance statistics and
        enrichment information.
```

# RCSB PDB REST API

```text
RCSBPDBClient
│
├── Search API
│   │
│   └── POST /rcsbsearch/v2/query
│       API:
│       https://search.rcsb.org/rcsbsearch/v2/query
│
│       Docs:
│       https://search.rcsb.org/
│
│       Purpose:
│       Search the PDB archive using structured queries,
│       including text, attributes, sequence similarity and
│       structure similarity.
│
│       Relict use:
│       Find protein structures matching a gene/protein,
│       sequence, ligand, organism or structural criterion.
│
│
├── Data API
│   │
│   ├── REST
│   │   │
│   │   └── GET /rest/v1/core/{object}/{id}
│   │       API:
│   │       https://data.rcsb.org/rest/v1/core/
│   │
│   │       Purpose:
│   │       Retrieve structured data for known PDB entries,
│   │       polymer entities, ligands, assemblies and other
│   │       structural objects.
│   │
│   │       Relict use:
│   │       Retrieve structure metadata, protein/chain identity,
│   │       ligand relationships and external cross-references.
│   │
│   │
│   └── GraphQL
│       │
│       └── POST /graphql
│           API:
│           https://data.rcsb.org/graphql
│
│           Purpose:
│           Retrieve flexible combinations of data across the
│           RCSB structural hierarchy.
│
│           Relict use:
│           Efficient multi-level protein → structure → ligand
│           and structure → annotation retrieval.
│
│
├── ModelServer
│   │
│   └── Structure Coordinates
│       API:
│       https://models.rcsb.org/
│
│       Docs:
│       https://models.rcsb.org/
│
│       Purpose:
│       Retrieve complete structures or selected subsets of
│       atomic coordinate data.
│
│       Supports:
│       ├── full structures
│       ├── assemblies
│       ├── polymer chains
│       ├── ligands
│       ├── residue surroundings
│       └── ligand surroundings
│
│       Relict use:
│       Retrieve atomic coordinates when structural analysis
│       or mutation/ligand-binding analysis is required.
│
│
├── Sequence Coordinates API
│   │
│   └── GraphQL
│       API:
│       [https://sequence-coordinates.rcsb.org/graphql](https://1d-coordinates.rcsb.org/graphql)
│
│       Purpose:
│       Provide mappings and alignments between structural
│       sequences and sequence databases including UniProt
│       and NCBI RefSeq.
│
│       Relict use:
│       Map protein residues and sequence positions between
│       UniProt, RefSeq and PDB structures.
│
│
└── Alignment API
    │
    └── Structure Alignment
        API:
        https://alignment.rcsb.org/
        
        Purpose:
        Programmatically perform 3D structural alignment
        between macromolecular structures.
        
        Relict use:
        Compare candidate protein structures and identify
        structural similarity.
```

# WIKIPATHWAYS SPARQL API

```
WikiPathwaysClient
│
├── SPARQL
│   │
│   └── SPARQL Endpoint
│       API:
│       https://sparql.wikipathways.org/sparql
│       Docs:
│       https://sandbox.wikipathways.org/sparql.html
│
│       Queries the WikiPathways RDF knowledge graph.
│
│       Used for:
│       ├── pathway lookup
│       ├── pathway → gene/protein relationships
│       ├── gene/protein → pathway relationships
│       ├── pathway → metabolite relationships
│       ├── pathway metadata
│       └── organism/pathway filtering
│
└── Pathway Data
    │
    ├── GPML
    │   API:
    │   https://data.wikipathways.org/current/gpml/
    │   Docs:
    │   https://sandbox.wikipathways.org/download.html
    │
    │   Current monthly GPML pathway releases.
    │   GPML contains the graphical/structural pathway
    │   representation, including pathway nodes and interactions.
    │
    └── GMT
        API:
        https://data.wikipathways.org/current/gmt/
        Docs:
        https://sandbox.wikipathways.org/download.html

        Current monthly GMT pathway-gene-set releases.
        Useful for pathway gene-set retrieval and
        enrichment workflows.
```


# GRAMENE REST API

```
GrameneClient
│
├── HTTP API
│   │
│   ├── Gene Search
│   │   └── GET /genes
│   │       API:
│   │       https://data.gramene.org/genes
│   │
│   │       Example:
│   │       https://data.gramene.org/genes?q=NAC001
│   │
│   │       Purpose:
│   │       Search Gramene gene annotations.
│   │
│   │       Relict use:
│   │       Resolve plant genes and retrieve annotation metadata.
│   │
│   │
│   ├── Gene Ontology Search
│   │   └── GET /GO
│   │       API:
│   │       https://data.gramene.org/GO
│   │
│   │       Example:
│   │       https://data.gramene.org/GO?q=NADP
│   │
│   │       Purpose:
│   │       Search Gramene GO annotations/terms.
│   │
│   │       Relict use:
│   │       Functional annotation and plant gene → GO relationships.
│   │
│   │
│   └── Ensembl Gene Lookup
│       └── GET /ensembl/lookup/id/{id}
│           API:
│           https://data.gramene.org/ensembl/lookup/id/{id}
│
│           Example:
│           https://data.gramene.org/ensembl/lookup/id/AT3G52430
│
│           Purpose:
│           Retrieve gene structure and annotation through
│           Gramene's Ensembl interface.
│
│           Relict use:
│           Plant gene identity, structure and annotation.
│
│
├── Plant Reactome
│   │
│   └── Content Service
│       └── GET /ContentService/data/pathways/top/{taxon_id}
│           API:
│           https://plantreactome.gramene.org/ContentService/data/pathways/top/{taxon_id}/
│
│           Example:
│           https://plantreactome.gramene.org/ContentService/data/pathways/top/4530/
│
│           Purpose:
│           Retrieve top-level Plant Reactome pathways for a taxon.
│
│           Relict use:
│           Plant gene → pathway context.
│
│
├── API Documentation
│   ├── https://news.gramene.org/web-services
│   └── https://data.gramene.org/
│
└── Public MySQL
    └── mysql-eg-publicsql.ebi.ac.uk:4157
        Purpose:
        Read-only Ensembl Genomes databases used by Gramene.

        Relict use:
        Optional direct database access; not required for
        the primary Gramene client.
```

# ANIMALQTLDB REST API

```
AnimalQTLdbClient
│
├── REST API
│   │
│   ├── Base API
│   │   https://www.animalgenome.org/cgi-bin/QTLdb/API
│   │
│   ├── Information
│   │   └── GET /iinfo
│   │       API:
│   │       https://www.animalgenome.org/cgi-bin/QTLdb/API/iinfo
│   │
│   │       Purpose:
│   │       Retrieve information about available QTLdb
│   │       data scopes and query context.
│   │
│   │
│   ├── Query
│   │   └── GET /iquery
│   │       API:
│   │       https://www.animalgenome.org/cgi-bin/QTLdb/API/iquery
│   │
│   │       Parameters include:
│   │       ├── q
│   │       ├── s
│   │       ├── h
│   │       └── history
│   │
│   │       Purpose:
│   │       Search QTLdb records by keywords and data scope.
│   │
│   │       Relict use:
│   │       Retrieve livestock QTL, traits, genes, breeds and
│   │       genomic-region associations.
│   │
│   │
│   └── Fetch
│       └── GET /ifetch
│           API:
│           https://www.animalgenome.org/cgi-bin/QTLdb/API/ifetch
│
│           Purpose:
│           Retrieve QTLdb records after identifying relevant
│           record identifiers.
│
│           Relict use:
│           Obtain detailed QTL/association records.
│
├── Data Scopes
│   ├── QTL
│   ├── Traits
│   ├── Publications
│   ├── Breeds
│   ├── Genes
│   └── Chromosomal locations
│
└── Output
    └── XML
        Purpose:
        Machine-readable API responses.
```

# FAANG REST API

```
FAANGClient
│
├── REST / Elasticsearch API
│   │
│   ├── Base API
│   │   https://data.faang.org/api/
│   │
│   ├── List Records
│   │   └── GET /{type}/_search/
│   │
│   │       API:
│   │       https://data.faang.org/api/{type}/_search/
│   │
│   │       Supported record types include:
│   │       ├── organism
│   │       ├── specimen
│   │       ├── dataset
│   │       ├── file
│   │       └── analysis
│   │
│   │       Purpose:
│   │       Search FAANG records using Elasticsearch queries.
│   │
│   │       Relict use:
│   │       Discover animal functional-genomics datasets,
│   │       samples and analyses.
│   │
│   │
│   ├── Record Detail
│   │   └── GET /{type}/{entityID}
│   │       API:
│   │       https://data.faang.org/api/{type}/{entityID}
│   │
│   │       Purpose:
│   │       Retrieve a specific FAANG record.
│   │
│   │       Relict use:
│   │       Retrieve detailed sample, experiment, file and
│   │       analysis metadata.
│   │
│   │
│   └── File Search
│       └── GET /file/_search/
│           API:
│           https://data.faang.org/api/file/_search/
│
│           Purpose:
│           Search files associated with FAANG samples,
│           experiments and studies.
│
│           Relict use:
│           Discover downloadable functional-genomics datasets.
│
├── Data Portal
│   └── https://data.faang.org/
│
└── API Documentation
    └── https://dcc-documentation.readthedocs.io/en/master/api/
```

# FARMGTEX

```
FarmGTExClient
│
├── Main Portal
│   └── https://www.farmgtex.org/
│
├── Web Servers
│   │
│   ├── CattleGTEx
│   │   └── https://cattlegtex.farmgtex.org/
│   │
│   ├── PigGTEx
│   │   └── https://piggtex.farmgtex.org/
│   │
│   ├── ChickenGTEx
│   │   └── https://chicken.farmgtex.org/
│   │
│   ├── TWAS Server
│   │   └── https://twas.farmgtex.org/
│   │
│   └── PigBiobank
│       └── https://pigbiobank.farmgtex.org/
│
├── Regulatory Variation
│   ├── eQTL
│   ├── sQTL
│   └── other molecular QTL
│
├── Molecular Phenotypes
│   ├── Gene expression
│   ├── Transcript regulation
│   └── Splicing
│
└── Downloads
    └── Species-specific datasets
        ├── CattleGTEx
        ├── PigGTEx
        ├── ChickenGTEx
        └── Other farm-animal resources
```

# BRENDA SOAP API

```
BRENDAClient
│
├── SOAP API
│   │
│   ├── Endpoint
│   │   https://www.brenda-enzymes.org/soap/brenda_server.php
│   │
│   ├── WSDL
│   │   https://www.brenda-enzymes.org/soap/brenda.wsdl
│   │
│   └── Python 3 WSDL
│       https://www.brenda-enzymes.org/soap/brenda_zeep.wsdl
│
│       Purpose:
│       Programmatic access to BRENDA enzyme data.
│
│       Relict use:
│       Retrieve enzyme function, reactions, substrates,
│       products, kinetics, inhibitors and organism context.
│
├── Enzyme Information
│   ├── EC number
│   ├── Enzyme names
│   ├── Organisms
│   ├── Molecular properties
│   └── Localization
│
├── Reaction / Substrate
│   ├── Substrates
│   ├── Products
│   ├── Cofactors
│   └── Ligands
│
├── Kinetics
│   ├── KM
│   ├── KCat
│   ├── KI
│   └── IC50
│
├── Regulation
│   ├── Inhibitors
│   ├── Activators
│   └── Metal ions
│
├── Protein Variants
│   └── Engineered / characterized variants
│
└── Access Requirements
    ├── Registration
    ├── Authentication
    └── Rate limit:
        approximately 1 request/second
```

# SABIO-RK REST API

```
SABIORKClient
│
├── REST API
│   │
│   ├── Base API
│   │   https://sabiork.h-its.org/sabioRestWebServices/
│   │
│   ├── Status
│   │   └── GET /status
│   │       API:
│   │       https://sabiork.h-its.org/sabioRestWebServices/status
│   │
│   ├── Database Version
│   │   └── GET /currentDatabaseVersion
│   │       API:
│   │       https://sabiork.h-its.org/sabioRestWebServices/currentDatabaseVersion
│   │
│   ├── Kinetic Law
│   │   └── GET /kineticLaws/{id}
│   │       API:
│   │       https://sabiork.h-its.org/sabioRestWebServices/kineticLaws/{id}
│   │
│   ├── Multiple Kinetic Laws
│   │   └── GET /kineticLaws
│   │       API:
│   │       https://sabiork.h-its.org/sabioRestWebServices/kineticLaws
│   │
│   ├── Search Kinetic Laws
│   │   └── GET/POST /searchKineticLaws/{format}
│   │
│   │       Supported formats include:
│   │       ├── sbml
│   │       ├── biopax
│   │       ├── matlab
│   │       ├── octave
│   │       ├── dot
│   │       └── entryIDs
│   │
│   ├── Reaction IDs
│   │   └── GET/POST /reactions/reactionIDs
│   │
│   ├── Reaction Details
│   │   └── GET /searchReactionDetails
│   │
│   ├── Reaction Participants
│   │   └── GET /searchReactionParticipants
│   │
│   ├── Compound Details
│   │   └── POST /searchCompoundDetails
│   │
│   ├── Compound Synonyms
│   │   └── POST /searchCompoundSynonyms
│   │
│   ├── Enzyme Synonyms
│   │   └── POST /searchEnzymeSynonyms
│   │
│   └── Pathway Synonyms
│       └── POST /searchPathwaySynonyms
│
└── Query
    └── /searchKineticLaws
        Purpose:
        Search biochemical reactions and kinetic-law records.

        Relict use:
        Retrieve experimentally measured biochemical
        parameters and reaction context.
```

# VECTORBASE/VEUPATHDB WDK REST API

```
VEuPathDBClient
│
├── WDK REST API
│   │
│   ├── API Documentation
│   │   https://veupathdb.org/service-api.html
│   │
│   ├── Record Types
│   │   └── GET /service/record-types
│   │       API:
│   │       https://vectorbase.org/vectorbase/service/record-types
│   │
│   │       Purpose:
│   │       Retrieve available VectorBase record types.
│   │
│   │
│   ├── Gene Record Type
│   │   └── GET /service/record-types/gene
│   │       API:
│   │       https://vectorbase.org/vectorbase/service/record-types/gene
│   │
│   │       Purpose:
│   │       Retrieve the schema and available searches/
│   │       attributes for gene records.
│   │
│   │
│   └── Record Searches
│       └── /service/record-types/{type}/searches/{search}
│
│           Purpose:
│           Execute predefined WDK searches and retrieve
│           record identifiers and selected attributes.
│
│           Relict use:
│           Search vector genes, genomic annotations,
│           phenotypes and related biological records.
│
├── Output Formats
│   ├── JSON
│   ├── AttributeTabular
│   ├── TableTabular
│   ├── FASTA
│   └── GFF3
│
├── VectorBase
│   ├── Vector genomes
│   ├── Genes
│   ├── Gene annotations
│   ├── Expression
│   ├── Variants
│   └── Comparative / functional data
│
└── Downloads
    └── VectorBase Current Release
        https://vectorbase.org/vectorbase/app/downloads/Current_Release/
```


# OPENTARGETS GRAPHQL API

```
OpenTargetsClient
│
└── GraphQL API
    │
    └── POST /api/v4/graphql
        API:
        https://api.platform.opentargets.org/api/v4/graphql
        Docs:
        https://platform-docs.opentargets.org/data-access/graphql-api
        Schema:
        https://api.platform.opentargets.org/api/v4/graphql
        GraphiQL:
        https://api.platform.opentargets.org/
        │
        ├── Target
        │   └── target(...)
        │       ├── target information
        │       ├── disease / phenotype associations
        │       ├── tractability
        │       ├── expression
        │       ├── genetic evidence
        │       └── supporting evidence
        │
        ├── Disease / Phenotype
        │   └── disease(...)
        │       ├── disease information
        │       ├── associated targets
        │       ├── known drugs
        │       └── supporting evidence
        │
        ├── Drug
        │   └── drug(...)
        │       ├── drug information
        │       ├── mechanisms of action
        │       ├── indications
        │       └── target relationships
        │
        ├── Variant
        │   └── variant(...)
        │       ├── variant information
        │       ├── population frequencies
        │       ├── consequences
        │       └── genetic evidence
        │
        └── Studies
            └── studies(...)
                ├── study information
                ├── associated traits
                ├── publications
                └── genetic evidence / credible sets
```


# CHEMBL REST API

```text
ChEMBLClient
│
└── REST API
    │
    └── ChEMBL Web Services
        API:
        https://www.ebi.ac.uk/chembl/api/data/
        Docs:
        https://www.ebi.ac.uk/chembl/api/data/docs
       
        Provides programmatic access to ChEMBL's
        bioactivity and drug-discovery data.
       
        Used for:
        ├── compound/molecule lookup
        ├── molecular structures and properties
        ├── bioactivity measurements
        ├── compound → target relationships
        ├── target → compound relationships
        ├── assay metadata and experimental context
        ├── drug → target mechanisms
        ├── drug → indication relationships
        ├── drug warnings
        ├── target/protein information
        ├── target classification
        ├── target components
        ├── compound similarity search
        ├── compound substructure search
        ├── structural-alert filtering
        ├── drug classification
        ├── metabolism information
        ├── cell-line context
        ├── tissue context
        ├── organism context
        └── literature/provenance for experimental observations
       
        Core resources:
        ├── /molecule/
        ├── /activity/
        ├── /target/
        ├── /target_component/
        ├── /assay/
        ├── /mechanism/
        ├── /drug/
        ├── /drug_indication/
        ├── /drug_warning/
        ├── /similarity/
        ├── /substructure/
        └── /compound_structural_alert/
```


# GBIF REST API

```
GBIFClient
│
├── Species
│   │
│   ├── Species Match
│   │   GET /v2/species/match
│   │   API:
│   │   https://api.gbif.org/v2/species/match
│   │
│   │   Docs:
│   │   https://techdocs.gbif.org/en/openapi/
│   │
│   │   Purpose:
│   │   Resolve scientific names and taxonomic identifiers to
│   │   GBIF taxonomic concepts.
│   │
│   │   Relict use:
│   │   Normalize species identity and connect species from
│   │   Ensembl, NCBI and other sources to GBIF occurrence data.
│   │
│   │
│   └── Species / Taxon
│       GET /v1/species/{usageKey}
│       API:
│       https://api.gbif.org/v1/species/
│
│       Docs:
│       https://techdocs.gbif.org/en/openapi/
│
│       Purpose:
│       Retrieve taxonomic/name-usage information for a GBIF
│       taxonomic concept.
│
│       Relict use:
│       Taxonomic metadata, identifiers, hierarchy and
│       species-level context.
│
│
├── Occurrence
│   │
│   ├── Search
│   │   GET /v1/occurrence/search
│   │   API:
│   │   https://api.gbif.org/v1/occurrence/search
│   │
│   │   Docs:
│   │   https://techdocs.gbif.org/en/openapi/
│   │
│   │   Purpose:
│   │   Search indexed biodiversity occurrence records using
│   │   taxonomic, geographic, temporal and other filters.
│   │
│   │   Relict use:
│   │   Species distribution, geographic range, historical
│   │   observations and ecological/population context.
│   │
│   │
│   └── Single Occurrence
│       GET /v1/occurrence/{gbifId}
│       API:
│       https://api.gbif.org/v1/occurrence/
│
│       Docs:
│       https://techdocs.gbif.org/en/openapi/
│
│       Purpose:
│       Retrieve a specific occurrence record by GBIF ID.
│
│       Relict use:
│       Inspect individual observations or specimen records
│       when record-level provenance is required.
│
│
└── Occurrence Downloads
    │
    └── Download API
        POST /v1/occurrence/download/request
        API:
        https://api.gbif.org/v1/occurrence/download/request

        Docs:
        https://techdocs.gbif.org/en/data-use/api-downloads

        Purpose:
        Asynchronously create large occurrence-data downloads.

        Relict use:
        Large-scale ecological or population analysis when
        occurrence search is insufficient.
```

# GTEX REST API

```text
GTExClient
│
├── Expression
│   │
│   ├── Gene Expression
│   │   └── GET /api/v2/expression/geneExpression
│   │       API:
│   │       https://gtexportal.org/api/v2/expression/geneExpression
│   │
│   │       Docs:
│   │       https://gtexportal.org/api/v2/docs
│   │
│   │       Purpose:
│   │       Retrieve gene-expression measurements across GTEx tissues.
│   │
│   │       Relict use:
│   │       Determine where a gene is expressed and compare
│   │       tissue-specific expression patterns.
│   │
│   │
│   ├── Median Gene Expression
│   │   └── GET /api/v2/expression/medianGeneExpression
│   │       API:
│   │       https://gtexportal.org/api/v2/expression/medianGeneExpression
│   │
│   │       Purpose:
│   │       Retrieve median gene-expression values across tissues.
│   │
│   │       Relict use:
│   │       Tissue-specific expression ranking and
│   │       target/tissue-context analysis.
│   │
│   │
│   ├── Clustered Median Gene Expression
│   │   └── GET /api/v2/expression/clusteredMedianGeneExpression
│   │       API:
│   │       https://gtexportal.org/api/v2/expression/clusteredMedianGeneExpression
│   │
│   │       Purpose:
│   │       Retrieve clustered median gene-expression profiles.
│   │
│   │       Relict use:
│   │       Compare expression patterns between tissues and
│   │       identify related tissue-expression profiles.
│   │
│   │
│   ├── Transcript Expression
│   │   └── GET /api/v2/expression/medianTranscriptExpression
│   │       API:
│   │       https://gtexportal.org/api/v2/expression/medianTranscriptExpression
│   │
│   │       Purpose:
│   │       Retrieve median transcript-level expression across tissues.
│   │
│   │       Relict use:
│   │       Transcript-specific expression analysis.
│   │
│   │
│   ├── Exon Expression
│   │   └── GET /api/v2/expression/medianExonExpression
│   │       API:
│   │       https://gtexportal.org/api/v2/expression/medianExonExpression
│   │
│   │       Purpose:
│   │       Retrieve median exon-level expression measurements.
│   │
│   │       Relict use:
│   │       Fine-grained expression and transcript/exon analysis.
│   │
│   │
│   └── Junction Expression
│       └── GET /api/v2/expression/medianJunctionExpression
│           API:
│           https://gtexportal.org/api/v2/expression/medianJunctionExpression
│
│           Purpose:
│           Retrieve median splice-junction expression data.
│
│           Relict use:
│           Investigate tissue-specific RNA splicing patterns.
│
│
├── eQTL / Genetic Regulation
│   │
│   ├── Single-Tissue eQTL
│   │   └── GET /api/v2/association/singleTissueEqtl
│   │       API:
│   │       https://gtexportal.org/api/v2/association/singleTissueEqtl
│   │
│   │       Purpose:
│   │       Retrieve significant single-tissue expression
│   │       quantitative trait loci (eQTLs).
│   │
│   │       Relict use:
│   │       Connect genetic variants to changes in gene
│   │       expression within specific tissues.
│   │
│   │
│   ├── Single-Tissue eQTL by Location
│   │   └── GET /api/v2/association/singleTissueEqtlByLocation
│   │       API:
│   │       https://gtexportal.org/api/v2/association/singleTissueEqtlByLocation
│   │
│   │       Purpose:
│   │       Retrieve eQTL associations for a genomic location.
│   │
│   │       Relict use:
│   │       Variant → gene regulatory evidence for genomic regions.
│   │
│   │
│   ├── eQTL Genes
│   │   └── GET /api/v2/association/egene
│   │       API:
│   │       https://gtexportal.org/api/v2/association/egene
│   │
│   │       Purpose:
│   │       Retrieve genes with significant eQTL associations.
│   │
│   │       Relict use:
│   │       Identify genes whose expression is genetically regulated.
│   │
│   │
│   ├── Multi-Tissue eQTL
│   │   └── GET /api/v2/association/metasoft
│   │       API:
│   │       https://gtexportal.org/api/v2/association/metasoft
│   │
│   │       Purpose:
│   │       Retrieve multi-tissue eQTL association results.
│   │
│   │       Relict use:
│   │       Identify genetic regulation shared across tissues.
│   │
│   │
│   ├── Independent eQTL
│   │   └── GET /api/v2/association/independentEqtl
│   │       API:
│   │       https://gtexportal.org/api/v2/association/independentEqtl
│   │
│   │       Purpose:
│   │       Retrieve conditionally independent eQTL associations.
│   │
│   │       Relict use:
│   │       Separate independent regulatory signals when
│   │       multiple variants influence the same gene.
│   │
│   │
│   └── Fine Mapping
│       └── GET /api/v2/association/fineMapping
│           API:
│           https://gtexportal.org/api/v2/association/fineMapping
│
│           Purpose:
│           Retrieve fine-mapping results for genetic regulatory
│           associations.
│
│           Relict use:
│           Prioritize variants likely to contribute to observed
│           gene-expression regulation.
│
│
├── sQTL / Splicing Regulation
│   │
│   ├── Single-Tissue sQTL
│   │   └── GET /api/v2/association/singleTissueSqtl
│   │       API:
│   │       https://gtexportal.org/api/v2/association/singleTissueSqtl
│   │
│   │       Purpose:
│   │       Retrieve significant single-tissue splicing
│   │       quantitative trait loci.
│   │
│   │       Relict use:
│   │       Connect variants to tissue-specific alternative splicing.
│   │
│   │
│   └── sQTL Genes
│       └── GET /api/v2/association/sgene
│           API:
│           https://gtexportal.org/api/v2/association/sgene
│
│           Purpose:
│           Retrieve genes with significant sQTL associations.
│
│           Relict use:
│           Identify genes whose splicing is genetically regulated.
│
│
├── Variant / Genetic Context
│   │
│   ├── Variant
│   │   └── GET /api/v2/dataset/variant
│   │       API:
│   │       https://gtexportal.org/api/v2/dataset/variant
│   │
│   │       Purpose:
│   │       Retrieve GTEx variant information.
│   │
│   │       Relict use:
│   │       Resolve and contextualize variants used in
│   │       expression and QTL analysis.
│   │
│   │
│   ├── Linkage Disequilibrium
│   │   └── GET /api/v2/dataset/ld
│   │       API:
│   │       https://gtexportal.org/api/v2/dataset/ld
│   │
│   │       Purpose:
│   │       Retrieve linkage-disequilibrium information.
│   │
│   │       Relict use:
│   │       Assess relationships between variants surrounding
│   │       regulatory signals.
│   │
│   │
│   └── Linkage Disequilibrium by Variant
│       └── GET /api/v2/dataset/ldByVariant
│           API:
│           https://gtexportal.org/api/v2/dataset/ldByVariant
│
│           Purpose:
│           Retrieve LD information associated with a specific variant.
│
│           Relict use:
│           Identify correlated variants around candidate
│           regulatory variants.
│
│
├── Reference / Gene Resolution
│   │
│   ├── Gene Search
│   │   └── GET /api/v2/reference/geneSearch
│   │       API:
│   │       https://gtexportal.org/api/v2/reference/geneSearch
│   │
│   │       Purpose:
│   │       Search the GTEx reference gene set.
│   │
│   │       Relict use:
│   │       Resolve gene symbols and identifiers before
│   │       retrieving GTEx data.
│   │
│   │
│   ├── Gene
│   │   └── GET /api/v2/reference/gene
│   │       API:
│   │       https://gtexportal.org/api/v2/reference/gene
│   │
│   │       Purpose:
│   │       Retrieve GTEx reference gene information.
│   │
│   │       Relict use:
│   │       Connect expression records to reference gene identifiers.
│   │
│   │
│   ├── Transcript
│   │   └── GET /api/v2/reference/transcript
│   │       API:
│   │       https://gtexportal.org/api/v2/reference/transcript
│   │
│   │       Purpose:
│   │       Retrieve GTEx reference transcript information.
│   │
│   │       Relict use:
│   │       Resolve transcript identifiers for transcript-level analysis.
│   │
│   │
│   ├── Exon
│   │   └── GET /api/v2/reference/exon
│   │       API:
│   │       https://gtexportal.org/api/v2/reference/exon
│   │
│   │       Purpose:
│   │       Retrieve GTEx reference exon information.
│   │
│   │       Relict use:
│   │       Resolve exon-level identifiers for expression and
│   │       splicing analysis.
│   │
│   │
│   ├── Feature
│   │   └── GET /api/v2/reference/features/{featureId}
│   │       API:
│   │       https://gtexportal.org/api/v2/reference/features/{featureId}
│   │
│   │       Purpose:
│   │       Retrieve reference information for a GTEx feature.
│   │
│   │       Relict use:
│   │       Resolve biological features used by downstream
│   │       expression/QTL queries.
│   │
│   │
│   ├── Neighboring Gene
│   │   └── GET /api/v2/reference/neighborGene
│   │       API:
│   │       https://gtexportal.org/api/v2/reference/neighborGene
│   │
│   │       Purpose:
│   │       Retrieve genes neighboring a genomic feature or location.
│   │
│   │       Relict use:
│   │       Provide genomic context for variant/regulatory analysis.
│   │
│   │
│   └── GWAS Catalog by Location
│       └── GET /api/v2/reference/gwasCatalogByLocation
│           API:
│           https://gtexportal.org/api/v2/reference/gwasCatalogByLocation
│
│           Purpose:
│           Retrieve GWAS Catalog associations around a genomic location.
│
│           Relict use:
│           Connect regulatory variants and genomic regions to
│           reported trait/disease associations.
│
│
├── Tissue Metadata
│   │
│   └── Tissue Site Detail
│       └── GET /api/v2/dataset/tissueSiteDetail
│           API:
│           https://gtexportal.org/api/v2/dataset/tissueSiteDetail
│
│           Purpose:
│           Retrieve GTEx tissue-site metadata and identifiers.
│
│           Relict use:
│           Normalize tissue identities and associate expression
│           measurements with biological tissue context.
│
│
└── Dataset Metadata
    │
    ├── Dataset Information
    │   └── GET /api/v2/metadata/dataset
    │       API:
    │       https://gtexportal.org/api/v2/metadata/dataset
    │
    │       Purpose:
    │       Retrieve GTEx dataset/release metadata.
    │
    │       Relict use:
    │       Record dataset-version provenance for retrieved evidence.
    │
    │
    └── Dataset Annotation
        └── GET /api/v2/dataset/annotation
            API:
            https://gtexportal.org/api/v2/dataset/annotation

            Purpose:
            Retrieve dataset annotation information.

            Relict use:
            Interpret metadata associated with GTEx datasets.
```


# GNOMAD GRAPHQL API

```
gnomADClient
│
├── GraphQL API
│   │
│   ├── Endpoint
│   │   https://gnomad.broadinstitute.org/api
│   │
│   │   Purpose:
│   │   Programmatic access to gnomAD variant and gene data.
│   │
│   │   Relict use:
│   │   Retrieve population-level variant evidence without
│   │   maintaining the complete gnomAD dataset locally.
│   │
│   ├── Variant
│   │   └── variant(...)
│   │
│   │       Purpose:
│   │       Retrieve information for a specific variant.
│   │
│   │       Relict use:
│   │       Variant-level allele frequency and population evidence.
│   │
│   └── Gene
│       └── gene(...)
│
│           Purpose:
│           Retrieve gene-level information and associated variants.
│
│           Relict use:
│           Gene → variant population evidence.
│
│
├── Population Frequency
│   │
│   ├── Allele Count (AC)
│   ├── Allele Number (AN)
│   ├── Allele Frequency (AF)
│   ├── Homozygote Count
│   └── Population-specific frequencies
│
│       Purpose:
│       Quantify variant frequency across gnomAD populations.
│
│       Relict use:
│       Determine whether variants are common, rare or
│       population-specific.
│
│
├── Population / Ancestry
│   │
│   └── Population-specific variant frequencies
│
│       Purpose:
│       Retrieve frequency information stratified by
│       available gnomAD populations.
│
│       Relict use:
│       Population-aware variant interpretation.
│
│
├── Constraint
│   │
│   ├── Gene constraint metrics
│   ├── Loss-of-function constraint
│   └── Missense constraint
│
│       Purpose:
│       Quantify gene intolerance to functional variation.
│
│       Relict use:
│       Prioritize genes and variants based on constraint evidence.
│
│
└── Structural Variation
    │
    └── gnomAD-SV
        │
        Purpose:
        Population-level structural variant data.
        
        Relict use:
        Structural-variant frequency and population evidence.
```


# TIMETREE REST API

```
TimeTreeClient
│
├── Official Website
│   https://timetree.org/
│
├── REST API
│   https://timetree.temple.edu/api/
│
├── Taxon Resolution
│   GET /taxon/{name}
│
│   Example:
│   https://timetree.temple.edu/api/taxon/human
│
├── Pairwise Divergence
│   GET /pairwise/{taxon1}/{taxon2}
│
│   Example:
│   https://timetree.temple.edu/api/pairwise/9606/10090
│
└── Complete Dataset
    └── Not a normal public bulk-download URL
        Complete timetree downloads require contacting TimeTree.
```

# SYNBIOHUB REST API

```
SynBioHubClient
│
├── Public API / Repository
│   │
│   ├── Main Instance
│   │   https://synbiohub.org/
│   │
│   └── API Instance
│       https://api.synbiohub.org/
│
│       Purpose:
│       Repository for synthetic-biology designs, biological
│       parts and engineered constructs represented using SBOL.
│
│       Relict use:
│       Retrieve standardized synthetic-biology designs,
│       parts, components and associated provenance.
│
│
├── Search
│   │
│   └── GET /search/
│       API:
│       https://api.synbiohub.org/search/
│
│       Example:
│       https://api.synbiohub.org/search/?q=Expression%20vector
│
│       Purpose:
│       Search public SynBioHub designs and parts.
│
│       Relict use:
│       Discover existing biological parts, constructs and
│       synthetic-biology designs.
│
│
├── Public Design
│   │
│   └── GET /public/{collection}/{id}/{version}
│       API:
│       https://api.synbiohub.org/public/{collection}/{id}/{version}
│
│       Purpose:
│       Retrieve a specific public design/component version.
│
│       Relict use:
│       Retrieve standardized design information and
│       design provenance.
│
│
├── Design Relationships
│   │
│   ├── /uses
│   └── /twins
│
│       Purpose:
│       Retrieve relationships between designs/components.
│
│       Relict use:
│       Construct → component and related-design relationships.
│
│
├── Data Formats
│   │
│   ├── SBOL
│   ├── GenBank
│   ├── GFF3
│   ├── FASTA
│   └── COMBINE Archive
│
│       Purpose:
│       Exchange synthetic-biology designs in standardized
│       and commonly used biological formats.
│
└── API Documentation
    ├── https://github.com/SynBioHub
    └── API documentation repositories maintained by
        the SynBioHub project
```


# EPIDB

```
EpiDBClient
│
├── Official Portal
│   └── https://epidb.animalgenome.org/
│
├── Metadata / Dataset Search
│   │
│   └── EpiDB web interface
│       https://epidb.animalgenome.org/
│
│       Purpose:
│       Search and explore processed livestock epigenomic and
│       gene-expression datasets and their metadata.
│
│       Relict use:
│       Discover livestock datasets relevant to tissue,
│       gene-expression and regulatory analysis.
│
│
├── Gene Expression
│   │
│   ├── Tissue-specific expression
│   ├── Baseline expression
│   └── Gene expression atlas
│
│       Purpose:
│       Provide processed gene-expression measurements across
│       livestock tissues.
│
│       Relict use:
│       Tissue-specific expression and agriculture-focused
│       regulatory analysis.
│
│
├── Species
│   │
│   └── Livestock datasets
│       ├── Cattle
│       ├── Chicken
│       ├── Pig
│       ├── Sheep
│       └── Horse
│
│       Purpose:
│       Provide species-specific processed functional-genomics
│       information.
│
│
├── Data Resources
│   └── /resource
│       API:
│       https://epidb.animalgenome.org/resource
│
│       Purpose:
│       Document external resources and reference datasets
│       used by EpiDB.
│
│       Relict use:
│       Dataset provenance and identification of underlying
│       genome/annotation resources.
│
└── Downloads
    │
    └── Public processed datasets
        Purpose:
        Retrieve EpiDB datasets for local analysis.

        Relict use:
        Optional ingestion into DuckDB for large-scale
        agriculture/regulatory analysis.
```
# HPA (Human Protein Atlas)

```
HumanProteinAtlasClient
│
├── Official Download Portal
│   https://www.proteinatlas.org/about/download
│
├── Main Search Dataset
│   │
│   ├── TSV
│   │   https://www.proteinatlas.org/download/proteinatlas.tsv.zip
│   │   │
│   │   └── Recommended for:
│   │       DuckDB ingestion
│   │
│   ├── JSON
│   │   https://www.proteinatlas.org/download/proteinatlas.json.gz
│   │
│   └── XML
│       https://www.proteinatlas.org/download/proteinatlas.xml.gz
│
├── Single Gene
│   │
│   ├── TSV
│   │   https://www.proteinatlas.org/{ENSEMBL_ID}.tsv
│   │
│   ├── JSON
│   │   https://www.proteinatlas.org/{ENSEMBL_ID}.json
│   │
│   └── XML
│       https://www.proteinatlas.org/{ENSEMBL_ID}.xml
│
└── Programmatic Access
    https://www.proteinatlas.org/about/download
```

# ALPHAMISSENSE

```
AlphaMissenseClient
│
├── Official Dataset
│   https://zenodo.org/records/10813168
│
├── Human Genome Predictions
│   │
│   ├── hg38
│   │   https://zenodo.org/records/10813168/files/AlphaMissense_hg38.tsv.gz?download=1
│   │   │
│   │   └── Recommended
│   │
│   └── hg19
│       https://zenodo.org/records/10813168/files/AlphaMissense_hg19.tsv.gz?download=1
│
├── Gene-level Predictions
│   │
│   ├── hg38
│   │   https://zenodo.org/records/10813168/files/AlphaMissense_gene_hg38.tsv.gz?download=1
│   │
│   └── hg19
│       https://zenodo.org/records/10813168/files/AlphaMissense_gene_hg19.tsv.gz?download=1
│
├── Amino-acid Substitutions
│   └── https://zenodo.org/records/10813168/files/AlphaMissense_aa_substitutions.tsv.gz?download=1
│
├── Non-canonical Isoforms
│   ├── hg38
│   │   https://zenodo.org/records/10813168/files/AlphaMissense_isoforms_hg38.tsv.gz?download=1
│   │
│   └── Amino-acid substitutions
│       https://zenodo.org/records/10813168/files/AlphaMissense_isoforms_aa_substitutions.tsv.gz?download=1
│
└── Metadata / Version
    https://zenodo.org/records/10813168
```

# DNA ZOO

```
DNAZooClient
│
├── Official Website
│   https://dnazoo.org/
│
├── Assembly Catalogue
│   https://www.dnazoo.org/assemblies/
│
├── Species Assembly
│   https://www.dnazoo.org/assemblies/{species}
│
└── Machine-readable / downloadable assembly files
    └── Obtained from the individual assembly's data-release links
```

# GENOME 10K

```
Genome10KClient
│
├── GenomeArk
│   https://www.genomeark.org/
│
├── Public S3 Bucket
│   s3://genomeark/
│
├── AWS ARN
│   arn:aws:s3:::genomeark
│
├── Anonymous CLI Access
│   aws s3 ls s3://genomeark/ --no-sign-request
│
└── Genome Data
    ├── FASTA
    ├── FASTQ
    ├── BAM
    ├── BED
    └── Assembly / project metadata
```

# VGP (Vertebrate Genome Project)

```
VGPClient
│
├── Official Project
│   https://vertebrategenomesproject.org/
│
├── GenomeArk
│   https://www.genomeark.org/
│
├── GenomeArk S3
│   s3://genomeark/
│
├── AWS ARN
│   arn:aws:s3:::genomeark
│
├── Anonymous Access
│   aws s3 ls s3://genomeark/ --no-sign-request
│
├── VGP Assembly Hub
│   https://hgdownload.soe.ucsc.edu/hubs/VGP/
│
└── VGP Genome Data
    ├── FASTA
    ├── FASTQ
    ├── BAM
    ├── assembly metadata
    └── annotation data
```


# EVO2

```
Evo2Client
│
├── Local Inference
│   │
│   ├── Official Repository
│   │   https://github.com/ArcInstitute/evo2
│   │
│   ├── Python Package
│   │   pip install evo2
│   │
│   ├── Models
│   │   ├── Evo 2 7B
│   │   ├── Evo 2 20B
│   │   └── Evo 2 40B
│   │
│   │   Model Weights:
│   │   https://huggingface.co/collections/arcinstitute/evo-2
│   │
│   │   Purpose:
│   │   Run Evo 2 locally for genomic sequence inference,
│   │   scoring, embeddings and generation.
│   │
│   │   Relict use:
│   │   Post-plan sequence analysis and model-derived
│   │   assessment of candidate genomic sequences.
│   │
│   └── Vortex Inference Engine
│       https://github.com/ArcInstitute/evo2
│
│       Purpose:
│       High-performance local Evo 2 inference.
│
│
├── Hosted Inference
│   │
│   └── NVIDIA NIM
│       │
│       ├── Evo 2 40B Forward
│       │   API:
│       │   https://health.api.nvidia.com/v1/biology/arc/evo2-40b/generate
│       │
│       │   Purpose:
│       │   Hosted Evo 2 inference without maintaining
│       │   the model locally.
│       │
│       │   Relict use:
│       │   Remote sequence scoring/generation.
│       │
│       └── NVIDIA Build
│           https://build.nvidia.com/arc/evo2-40b
│
│
├── Sequence Analysis
│   │
│   ├── Sequence Scoring
│   │   Purpose:
│   │   Calculate model-based sequence scores.
│   │
│   │   Relict use:
│   │   Compare reference and post-plan genomic sequences.
│   │
│   ├── Embeddings
│   │   Purpose:
│   │   Generate sequence representations from Evo 2.
│   │
│   │   Relict use:
│   │   Sequence-level representation and downstream analysis.
│   │
│   └── Sequence Generation
│       Purpose:
│       Generate genomic sequence continuations/designs.
│
│       Relict use:
│       Exploratory sequence-design analysis.
│
└── Training Dataset
    │
    └── OpenGenome2
        https://huggingface.co/datasets/arcinstitute/opengenome2

        Purpose:
        Dataset used for Evo 2 pretraining.

        Relict use:
        Provenance/reference only; not required for normal
        Evo 2 inference.
```


# CRISPOR

```
CRISPORClient
│
├── Local / CLI
│   │
│   ├── Official Repository
│   │   https://github.com/maximilianh/crisporWebsite
│   │
│   ├── CLI
│   │   crispor.py
│   │
│   │   Input:
│   │   ├── Genome
│   │   └── FASTA sequence
│   │
│   │   Output:
│   │   └── Guide table
│   │
│   │   Purpose:
│   │   Run CRISPOR locally for guide identification,
│   │   scoring and off-target analysis.
│   │
│   │   Relict use:
│   │   Generate candidate guides and retrieve guide-level
│   │   specificity/efficiency information.
│   │
│   └── CRISPOR Efficiency Scoring
│       └── crisporEffScores.py
│
│       Purpose:
│       Calculate guide efficiency scores without performing
│       the complete genome search.
│
│       Relict use:
│       Fast guide-ranking stage.
│
│
├── Guide Design
│   │
│   ├── PAM identification
│   ├── Guide sequence identification
│   ├── On-target efficiency scoring
│   └── Guide ranking
│
│       Relict use:
│       Candidate guide generation and prioritization.
│
│
├── Off-Target Analysis
│   │
│   ├── Genome-wide matching
│   ├── Mismatch analysis
│   ├── CFD scoring
│   └── Specificity scoring
│
│       Relict use:
│       Post-design off-target assessment.
│
└── Primer / Cloning Support
    │
    └── Primer design
        Purpose:
        Generate primers associated with selected guides.

        Relict use:
        Optional downstream experimental-design information.
```


# CHOPCHOP

```
CHOPCHOPClient
│
├── Local / CLI
│   │
│   ├── Official Repository
│   │   https://bitbucket.org/valenlab/chopchop
│   │
│   ├── Main Program
│   │   └── chopchop.py
│   │
│   └── Command Line Interface
│       Purpose:
│       Run CHOPCHOP locally for guide-design analysis.
│
│       Relict use:
│       Independent second guide-design/scoring source.
│
│
├── Guide Design
│   │
│   ├── Target gene / region
│   ├── Coding sequence
│   ├── Promoter
│   ├── UTR
│   └── Splice regions
│
│       Relict use:
│       Generate candidate guides for different target regions.
│
│
├── Guide Scoring
│   │
│   ├── On-target scoring
│   └── Guide ranking
│
│       Relict use:
│       Independent guide prioritization.
│
│
├── Off-Target Analysis
│   │
│   └── Genome-wide off-target search
│
│       Relict use:
│       Independent off-target evidence for comparison
│       against CRISPOR.
│
└── Supported Editing Modes
    │
    ├── Knockout
    ├── Activation
    └── Other supported CRISPR targeting workflows

        Relict use:
        Generate candidates appropriate to the selected
        editing objective.
```
