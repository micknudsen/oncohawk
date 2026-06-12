import argparse
import pyranges as pr
import json
import pandas as pd


class GTFPanelBuilder:
    """
    Build panel BED from GTF and JSON gene selection config.

    JSON format:
    {
        "genes": [
            {
                "hgnc_id": "HGNC:6342",
                "gene_name": "KIT",
                "transcripts": [
                    {
                        "transcript_id": "ENST00000288135",
                        "cds": "all"
                    },
                    {
                        "transcript_id": "ENST00000288136",
                        "cds": [1, 2, 5]
                    }
                ]
            }
        ]
    }

    Output: BED6 file with regions (CDS selected or all exons).
    """

    def __init__(self, gtf_path):
        """Load and parse GTF file."""
        self.gtf = pr.read_gtf(gtf_path)
        self.cds_engine = CDSOrderingEngine(self.gtf)
        self._build_gene_map()

    def _build_gene_map(self):
        """Map HGNC gene name to gene_id."""
        self.gene_map = {}
        genes = self.gtf[self.gtf.Feature == "gene"]
        for record in genes.df.itertuples():
            gene_name = record.gene_name
            gene_id = record.gene_id
            if gene_name not in self.gene_map:
                self.gene_map[gene_name] = gene_id

    def build_from_json(self, json_path):
        """
        Parse JSON config and build panel BED.

        Returns: PyRanges with bed-like structure (chrom, start, end, name, score, strand)
        """
        with open(json_path) as f:
            config = json.load(f)

        bed_list = []

        for gene_entry in config.get("genes", []):
            gene_name = gene_entry.get("gene_name")
            gene_id = self.gene_map.get(gene_name)

            if not gene_id:
                raise ValueError(f"Gene {gene_name} not found in GTF")

            for transcript_entry in gene_entry.get("transcripts", []):
                transcript_id = transcript_entry.get("transcript_id")
                cds_spec = transcript_entry.get("cds")

                # Get CDS features for this transcript
                cds_ranges = self.cds_engine.build_cds_index(gene_id, transcript_id)

                if len(cds_ranges) == 0:
                    continue

                cds_df = cds_ranges.df.copy()

                # Filter by CDS spec if not "all"
                if cds_spec == "all":
                    pass
                elif isinstance(cds_spec, list):
                    cds_df = cds_df[cds_df["cds_index"].isin(cds_spec)]
                else:
                    raise ValueError(
                        f"Invalid cds spec for {transcript_id}: {cds_spec!r}. "
                        "Expected 'all' or list of CDS indexes."
                    )

                # Build BED entries
                for _, row in cds_df.iterrows():
                    bed_list.append(
                        {
                            "Chromosome": row["Chromosome"],
                            "Start": row["Start"],
                            "End": row["End"],
                            "Name": f"{gene_name}_{transcript_id}_{row['cds_index']}",
                            "Score": 0,
                            "Strand": row["Strand"],
                        }
                    )

        if not bed_list:
            raise ValueError("No CDS regions found for specified genes/transcripts")

        bed_df = pd.DataFrame(bed_list)
        # Sort by chromosome and start position
        bed_df = bed_df.sort_values(["Chromosome", "Start"]).reset_index(drop=True)

        return pr.PyRanges(bed_df)


class CDSOrderingEngine:
    """
    STRICT GENCODE CDS ordering engine.

    Assumptions:
    - exon_number is ALWAYS present
    - exon_number defines transcript order
    - no coordinate-based inference allowed
    """

    def __init__(self, gtf):
        self.gtf = gtf
        self.cds = gtf[gtf.Feature == "CDS"]

    # ---------------------------------------------------
    # Build ordered CDS for transcript
    # ---------------------------------------------------
    def build_cds_index(self, gene_id, transcript_id):

        cds = self._get_cds(gene_id, transcript_id)

        if len(cds) == 0:
            return cds

        df = cds.df.copy()

        # HARD REQUIREMENT
        if "exon_number" not in df.columns:
            raise ValueError(
                f"Missing exon_number for {transcript_id}. "
                "GENCODE contract violated."
            )

        # enforce strict typing
        df["cds_index"] = df["exon_number"].astype(int)

        # sanity check: uniqueness within transcript
        if df["cds_index"].duplicated().any():
            raise ValueError(f"Duplicate exon_number detected in {transcript_id}")

        return pr.PyRanges(df)

    # ---------------------------------------------------
    def _get_cds(self, gene_id, transcript_id):
        return self.cds[
            (self.cds.gene_id == gene_id) & (self.cds.transcript_id == transcript_id)
        ]


parser = argparse.ArgumentParser()

parser.add_argument("--gtf", required=True)
parser.add_argument("--config", required=True)
parser.add_argument("--out", required=True)

args = parser.parse_args()

builder = GTFPanelBuilder(args.gtf)
bed = builder.build_from_json(args.config)

# Write BED file
bed.df.to_csv(
    args.out,
    sep="\t",
    header=False,
    index=False,
    columns=["Chromosome", "Start", "End", "Name", "Score", "Strand"],
)
