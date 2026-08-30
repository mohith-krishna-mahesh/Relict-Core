"""
Domain configs for Relict Core Task 1 (Objective Resolution) dataset generation.

Each entry provides the word banks needed to generate realistic, domain-flavored
objectives for all 4 structural categories (standard_clear, direction_ambiguous,
fully_vague, multi_goal_clear). Domain is NOT stored as a field on any generated
record and is NOT part of the trained schema -- it exists purely to diversify
generation so the model doesn't overfit ambiguity/clarity judgments to
agriculture-specific phrasing. ProjectContext.scope (Shell-supplied) is the
real domain signal at inference time; these configs just make sure training
data covers the range of scopes Shell will actually send.

Per-domain target counts, matching the validated agriculture ratio, scaled to
~1000 records/domain (6 domains x 1000 = ~6000 total):
    standard_clear:      300  (30%)
    direction_ambiguous: 300  (30%) -- ALWAYS via direction_ambiguous_generator.py,
                                        never via LLM generation (confirmed unreliable,
                                        3 separate attempts, ~0-30% correct at best)
    fully_vague:         200  (20%)
    multi_goal_clear:    200  (20%)
"""

DEFAULT_CATEGORY_TARGETS = {
    "standard_clear": 300,
    "direction_ambiguous": 300,
    "fully_vague": 200,
    "multi_goal_clear": 200,
}

DOMAINS = {
    "conservation": {
        "label": "Conservation",
        "description": (
            "Endangered species and wildlife genomics: improving disease resistance, "
            "genetic diversity, fertility, or environmental tolerance in at-risk "
            "extant species without compromising long-term population viability."
        ),
        "species": [
            "Panthera tigris (tiger)",
            "Ailuropoda melanoleuca (giant panda)",
            "Gymnogyps californianus (California condor)",
            "Diceros bicornis (black rhinoceros)",
            "Physeter macrocephalus (sperm whale)",
            "Vulpes lagopus (Arctic fox)",
            "Rhincodon typus (whale shark)",
            "Strigops habroptilus (kakapo)",
            "Ceratotherium simum cottoni (northern white rhinoceros)",
        ],
        "genes_traits": [
            "MHC diversity loci", "disease-resistance alleles", "cold-tolerance genes",
            "thermal-stress response genes", "reproductive-fitness alleles",
            "heterozygosity-linked loci", "immune-response genes",
        ],
        "phenotypes": [
            "disease resistance", "fertility", "cold tolerance", "immune robustness",
            "genetic diversity", "population viability", "thermal tolerance",
        ],
        "processes": [
            "immune response", "thermoregulation", "reproduction",
            "inbreeding depression mitigation", "stress-hormone regulation",
        ],
        "constraints": [
            "preserve genetic diversity", "avoid reducing population fitness",
            "maintain natural behavior", "preserve migratory capability",
            "avoid introducing novel alleles absent from the wild population",
        ],
        "ambiguous_parameters": [
            "immune gene expression level", "heterozygosity level",
            "thermal tolerance threshold", "disease susceptibility marker frequency",
            "reproductive hormone level",
        ],
    },
    "de-extinction": {
        "label": "De-extinction",
        "description": (
            "Extinct taxa and ancient DNA comparisons: reconstructing or "
            "approximating ancestral phenotypes in a living proxy/host species "
            "using ancient-DNA-informed edits."
        ),
        "species": [
            "Mammuthus primigenius (woolly mammoth)",
            "Thylacinus cynocephalus (thylacine)",
            "Raphus cucullatus (dodo)",
            "Equus quagga quagga (quagga)",
            "Capra pyrenaica pyrenaica (bucardo / Pyrenean ibex)",
            "Elephas maximus (Asian elephant, proxy host)",
            "Bos primigenius (aurochs)",
        ],
        "genes_traits": [
            "cold-adapted hemoglobin variants", "pigmentation genes",
            "hair-length/density genes", "subcutaneous fat regulatory genes",
            "ancestral-variant reconstruction targets", "ear/appendage-size genes",
        ],
        "phenotypes": [
            "cold tolerance", "coat/fur texture", "body size",
            "hemoglobin oxygen affinity", "subcutaneous fat proportion",
        ],
        "processes": [
            "cold adaptation", "pigmentation", "thermogenesis",
            "ancient-DNA variant reconstruction", "developmental patterning",
        ],
        "constraints": [
            "preserve fertility", "match ancestral phenotype as closely as possible",
            "use the closest extant relative as host", "avoid non-ancestral traits",
            "limit edits to loci with high-confidence ancient-DNA support",
        ],
        "ambiguous_parameters": [
            "hair density", "hemoglobin oxygen affinity", "body-fat proportion",
            "cold-shock response magnitude", "pigmentation intensity",
        ],
    },
    "agriculture": {
        "label": "Agriculture",
        "description": (
            "Livestock and plant breeding / traits: improving yield, resistance, "
            "or quality traits in domesticated crop and livestock species."
        ),
        "species": [
            "Zea mays (maize)", "Oryza sativa (rice)", "Bos taurus (cattle)",
            "Gallus gallus (chicken)", "Sus scrofa domesticus (pig)",
            "Solanum lycopersicum (tomato)", "Glycine max (soybean)",
            "Musa acuminata (banana)",
        ],
        "genes_traits": [
            "yield-associated genes", "drought-tolerance genes",
            "disease-resistance loci", "flowering-time genes",
            "milk-yield QTLs", "feed-conversion genes", "fruit-ripening genes",
        ],
        "phenotypes": [
            "yield", "drought tolerance", "disease resistance", "flowering time",
            "milk yield", "growth rate", "fruit firmness",
        ],
        "processes": [
            "flowering regulation", "drought stress response",
            "disease resistance signaling", "growth regulation", "fruit ripening",
        ],
        "constraints": [
            "preserve yield", "maintain nutritional quality",
            "avoid affecting fertility", "preserve flavor profile",
            "maintain compatibility with existing breeding lines",
        ],
        "ambiguous_parameters": [
            "flowering time", "grain size", "root depth",
            "feed conversion ratio", "fruit ripening rate",
        ],
    },
    "synthetic-biology": {
        "label": "Synthetic Biology",
        "description": (
            "Metabolic circuits and enzyme kinetics: engineering microbial or "
            "cell-based chassis organisms for biosynthetic pathway performance."
        ),
        "species": [
            "Escherichia coli", "Saccharomyces cerevisiae", "Bacillus subtilis",
            "Pseudomonas putida", "Chlamydomonas reinhardtii",
            "Corynebacterium glutamicum",
        ],
        "genes_traits": [
            "enzyme kinetic parameters (Km/Vmax)", "pathway-flux genes",
            "biosynthetic operon components", "promoter-strength elements",
            "substrate-transporter genes", "regulatory feedback-loop genes",
        ],
        "phenotypes": [
            "metabolite yield", "pathway flux", "enzyme turnover rate",
            "substrate specificity", "product titer",
        ],
        "processes": [
            "metabolic flux regulation", "enzyme catalysis",
            "gene circuit regulation", "biosynthetic pathway engineering",
            "feedback inhibition",
        ],
        "constraints": [
            "minimize metabolic burden", "maintain host viability",
            "avoid toxic intermediate accumulation", "preserve genetic stability",
            "keep the circuit orthogonal to native regulatory networks",
        ],
        "ambiguous_parameters": [
            "enzyme turnover rate", "pathway flux", "promoter strength",
            "metabolite titer", "substrate affinity",
        ],
    },
    "population-control": {
        "label": "Population Control",
        "description": (
            "Disease vectors and gene drives: suppressing or modifying wild "
            "populations of disease-vector or invasive species."
        ),
        "species": [
            "Anopheles gambiae (malaria mosquito)", "Aedes aegypti (dengue/Zika mosquito)",
            "Rattus norvegicus (invasive rat)", "Mus musculus (invasive mouse)",
            "Culex quinquefasciatus (mosquito)",
        ],
        "genes_traits": [
            "gene-drive constructs", "sterility genes", "vector-competence genes",
            "fertility-suppression alleles", "sex-ratio distorter genes",
        ],
        "phenotypes": [
            "vector competence", "fertility", "population growth rate",
            "pathogen transmission capacity", "sex-ratio bias",
        ],
        "processes": [
            "gene-drive propagation", "fertility suppression",
            "pathogen transmission", "population suppression",
            "sex determination",
        ],
        "constraints": [
            "restrict spread to the target population", "avoid cross-species drive",
            "preserve the ecological role of non-target species",
            "ensure reversibility", "limit drive persistence beyond N generations",
        ],
        "ambiguous_parameters": [
            "drive inheritance rate", "vector competence level",
            "population suppression rate", "transmission efficiency",
            "sex-ratio bias magnitude",
        ],
    },
    "precision-medicine": {
        "label": "Precision Medicine",
        "description": (
            "Human therapeutics and variant effects: correcting or modulating "
            "disease-associated variants or drug-response pathways in humans."
        ),
        "species": ["Homo sapiens"],
        "genes_traits": [
            "BRCA1/BRCA2", "CFTR", "PCSK9", "HBB", "LDLR",
            "pathogenic ClinVar variant alleles", "pharmacogenomic variants",
        ],
        "phenotypes": [
            "disease risk", "drug response", "protein function",
            "variant pathogenicity", "enzyme activity",
        ],
        "processes": [
            "variant effect prediction", "drug metabolism",
            "disease-risk modulation", "gene therapy correction",
            "protein folding",
        ],
        "constraints": [
            "restrict to somatic cells", "avoid germline modification",
            "preserve protein function outside the target region",
            "minimize off-target effects", "comply with therapeutic safety margins",
        ],
        "ambiguous_parameters": [
            "variant pathogenicity score", "drug metabolism rate",
            "protein expression level", "disease risk magnitude",
            "enzyme activity level",
        ],
    },
}


def get_domain(key: str) -> dict:
    if key not in DOMAINS:
        raise KeyError(f"Unknown domain '{key}'. Valid keys: {sorted(DOMAINS)}")
    return DOMAINS[key]