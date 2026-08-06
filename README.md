# Empirical Conversational Programming

Replication package for the paper "Programming by Chat: A Large-Scale Behavioral Analysis of 11,579 Real-World AI-Assisted IDE Sessions", accepted at the 41st IEEE/ACM International Conference on Automated Software Engineering (ASE 2026). The full paper is available on [arXiv](https://arxiv.org/abs/2604.00436).

> The data scraping and parsing scripts are available at [TTangNingzhi/vibe-coding-scraper](https://github.com/TTangNingzhi/vibe-coding-scraper).

## Repository Structure

- `data_scraping/`: Scrape and parse raw chat-history traces and GitHub metadata into structured JSON files.
- `intent_classification/`: Classifies the behavioral intent of each user message based on an [established taxonomy](intent_classification/codebook.txt) and analyzes the distribution of behavioral intent categories. Results are saved to `data/classifications/`.
    > **Note**: Intent classification is a prerequisite for most other analyses, which generally depend on `data/classifications/classifications_for_analysis.csv`. See the full [data specification](intent_classification/data_spec.md).
- `session_clustering/`: Clusters user sessions based on their sequence of behavioral intent categories. Results are saved to `data/clusters/` (including pre-computed distances). An interactive t-SNE visualization is accessible [here](https://conversational-programming-clusters.netlify.app/).
- `sub_classification/`: Further classifies messages within specific behavioral intent categories (e.g., sentiment expression) based on finer-grained needs. Results are saved to `data/sub_classifications/`.
- `markov_transition/`: Analyzes lift-weighted Markov transition probabilities between behavioral intent categories, both within sessions and across session boundaries.
- `session_evolution/`: Analyzes the evolution of user messages within sessions and session-level statistics across projects, in terms of behavioral intent category distribution, message/session length, and related metrics.
- `lang_detection/`: Detects natural and programming languages in text and diff blocks and analyzes their distributions. Results are saved to `data/detected_langs/`.
- `supplementary_stats/`: Ad hoc analyses, e.g., message distribution, repository characteristics, classification validation. Some notable files:
    - `repo_characteristics.ipynb`: Analyzes repository characteristics from the scraped data. Results are saved to `data/repo_characteristics.csv` (see the [data specification](supplementary_stats/repo_characteristics_spec.md)).
    - `ad_hoc_stats.ipynb`: Calculates various statistics from the data, such as message length distribution, opening versus non-opening message distribution, short versus long session distribution, and short-range continuity of behavioral intent categories.
    - `all_annotated_labels.csv`: Labels for sampled messages, including the raw LLM predictions and the manual labels from two human annotators.
    - `correctness_validation.ipynb`: Samples messages from each category and calculates inter-rater agreement and the correctness of LLM classifications.

## Data

All data should be placed under the `data/` directory. The full data structure is as follows:
```
data/
├── classifications/          # Behavioral intent classification results
├── clusters/                 # Session clustering results and pre-computed distances
├── contents/                 # Raw chat-history blobs (base64)
├── sub_classifications/      # Sub-classification results
├── detected_langs/           # Language detection results
├── repo_characteristics.csv  # Repository-level characteristics
├── repositories.json         # Repository metadata (stars, forks, language, etc.)
├── metadata.json             # Dataset metadata (scrape date, author)
├── searches/                 # Raw GitHub search results
├── searches.json             # Combined search records
├── mapping.csv               # Session-to-repository mapping table
├── markdowns/                # Raw chat-history Markdown files
├── markdowns_cli/            # CLI-agent style chat traces
├── parsed_chats/             # Structured parsed chat records
├── parsed_chats_simple/      # Simplified parsed chats
├── parsed_chats_simple_cli/  # Simplified CLI chat outputs
├── contributors/             # Repository contributor lists
├── readmes/                  # Repository README files
├── file_trees/               # Repository file trees
├── commits/                  # Commit-level payloads with patches
├── commits_path/             # Per-file commit histories
├── commits_history/          # Full repository commit histories
└── languages.json            # Repository language statistics
```

Due to copyright and privacy considerations (most source repositories do not carry explicit redistribution licenses), raw data (including chat sessions and repository characteristics) are not included in this package; only aggregated analysis results are retained. However, the data can be fully recollected via the [provided scraping pipeline](https://github.com/TTangNingzhi/vibe-coding-scraper). Researchers interested in accessing the raw data or discussing the project are welcome to contact [Ningzhi Tang](https://www.nztang.com/).

## Citation

If you use this package, please cite our paper:
```bibtex
@inproceedings{tang2026programming,
  title={Programming by Chat: A Large-Scale Behavioral Analysis of 11,579 Real-World AI-Assisted IDE Sessions},
  author={Tang, Ningzhi and Chen, Chaoran and Fang, Zihan and Xu, Gelei and Dhakal, Maria and Shi, Yiyu and McMillan, Collin and Huang, Yu and Li, Toby Jia-Jun},
  booktitle={2026 41st IEEE/ACM International Conference on Automated Software Engineering (ASE)},
  year={2026}
}
```

## Acknowledgments

This research was supported in part by a Google Cloud Research Credit Award, a Google Research Scholar Award, a gift from Adobe, an Edison Innovation Fellowship from the Notre Dame IDEA Center, and NSF grants CCF-2211428, CCF-2315887, CCF-2100035, CCF-2211429, CCF-2442682, and DGE-2622415. Any opinions, findings, or recommendations expressed here are those of the authors and do not necessarily reflect the views of the sponsors. The authors thank Yuqi Wang from CREVIK for introducing us to SpecStory, without which this study would not have been possible.