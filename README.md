# llm-graph-builder-offline

[![GitHub last commit](https://img.shields.io/github/last-commit/NotYuSheng/ChannelGPT-Tool?color=red)](#)

> [!WARNING]
> This project is a work in progress and is currently non-functional.

## Populate Volumes

1. Start neo4j in an offline environment

2. Populate volume

   Copy Sentence Transformer 
   ```
   docker cp neo4j-backend:/root/.cache/huggingface/hub/models--sentence-transformers--all-MiniLM-L6-v2 ./models--sentence-transformers--all-MiniLM-L6-v2
   ```

3. Theses will be populated and generated automatically for the online version. Just copy the folders over
   ```
   - ./llm-graph-builder/frontend:/code
   - ./llm-graph-builder/backend:/code
   ```
