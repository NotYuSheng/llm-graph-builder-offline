import logging
from langchain.docstore.document import Document
import os
from langchain_openai import ChatOpenAI, AzureChatOpenAI
from langchain_google_vertexai import ChatVertexAI
from langchain_groq import ChatGroq
from langchain_google_vertexai import HarmBlockThreshold, HarmCategory
from langchain_experimental.graph_transformers.diffbot import DiffbotGraphTransformer
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
from langchain_experimental.graph_transformers import LLMGraphTransformer
from langchain_core.prompts import ChatPromptTemplate
from langchain_anthropic import ChatAnthropic
from langchain_fireworks import ChatFireworks
from langchain_aws import ChatBedrock
from langchain_community.chat_models import ChatOllama
import boto3
import google.auth
from src.shared.constants import MODEL_VERSIONS, PROMPT_TO_ALL_LLMs


def get_llm(model: str):
    """Retrieve the specified language model based on the model name."""
    env_key = "LLM_MODEL_CONFIG_" + model
    env_value = os.environ.get(env_key)
    logging.info("Model: {}".format(env_key))

    if "gemini" in model:
        model_name = env_value
        credentials, project_id = google.auth.default()
        #model_name = MODEL_VERSIONS[model]
        llm = ChatVertexAI(
            model_name=model_name,
            #convert_system_message_to_human=True,
            credentials=credentials,
            project=project_id,
            temperature=0,
            safety_settings={
                HarmCategory.HARM_CATEGORY_UNSPECIFIED: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            },
        )

    elif "vllm_sealion" in model:
        model_name, api_key = "sealion", "token-abc123"
        llm = ChatOpenAI(
            openai_api_base="http://vllm_sealion:8000/v1",
            api_key=api_key,
            model=model_name,
            temperature=0,
        )

    elif "vllm_qwen" in model:
        model_name, api_key = "qwen2.5", "token-abc123"
        llm = ChatOpenAI(
            openai_api_base="http://vllm_qwen2.5:8000/v1",
            api_key=api_key,
            model=model_name,
            temperature=0,
        )

    elif "ollama_llama3" in model:
        model_name, base_url = "llama3:instruct", "http://ollama:11434"
        llm = ChatOllama(base_url=base_url, model=model_name)

    elif "azure" in model:
        model_name, api_endpoint, api_key, api_version = env_value.split(",")
        llm = AzureChatOpenAI(
            api_key=api_key,
            azure_endpoint=api_endpoint,
            azure_deployment=model_name,  # takes precedence over model parameter
            api_version=api_version,
            temperature=0,
            max_tokens=None,
            timeout=None,
        )

    elif "anthropic" in model:
        model_name, api_key = env_value.split(",")
        llm = ChatAnthropic(
            api_key=api_key, model=model_name, temperature=0, timeout=None
        )

    elif "fireworks" in model:
        model_name, api_key = env_value.split(",")
        llm = ChatFireworks(api_key=api_key, model=model_name)

    elif "groq" in model:
        model_name, base_url, api_key = env_value.split(",")
        llm = ChatGroq(api_key=api_key, model_name=model_name, temperature=0)

    elif "bedrock" in model:
        model_name, aws_access_key, aws_secret_key, region_name = env_value.split(",")
        bedrock_client = boto3.client(
            service_name="bedrock-runtime",
            region_name=region_name,
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
        )

        llm = ChatBedrock(
            client=bedrock_client, model_id=model_name, model_kwargs=dict(temperature=0)
        )

    elif "diffbot" in model:
        #model_name = "diffbot"
        model_name, api_key = env_value.split(",")
        llm = DiffbotGraphTransformer(
            diffbot_api_key=api_key,
            extract_types=["entities", "facts"],
        )

    else: 
        model_name, api_endpoint, api_key = env_value.split(",")
        llm = ChatOpenAI(
            api_key=api_key,
            base_url=api_endpoint,
            model=model_name,
            temperature=0,
        )
            
    logging.info(f"Model created - Model Version: {model}")
    return llm, model_name


def get_combined_chunks(chunkId_chunkDoc_list):
    chunks_to_combine = int(os.environ.get("NUMBER_OF_CHUNKS_TO_COMBINE"))
    logging.info(f"Combining {chunks_to_combine} chunks before sending request to LLM")
    combined_chunk_document_list = []
    combined_chunks_page_content = [
        "".join(
            document["chunk_doc"].page_content
            for document in chunkId_chunkDoc_list[i : i + chunks_to_combine]
        )
        for i in range(0, len(chunkId_chunkDoc_list), chunks_to_combine)
    ]
    combined_chunks_ids = [
        [
            document["chunk_id"]
            for document in chunkId_chunkDoc_list[i : i + chunks_to_combine]
        ]
        for i in range(0, len(chunkId_chunkDoc_list), chunks_to_combine)
    ]

    for i in range(len(combined_chunks_page_content)):
        combined_chunk_document_list.append(
            Document(
                page_content=combined_chunks_page_content[i],
                metadata={"combined_chunk_ids": combined_chunks_ids[i]},
            )
        )
    return combined_chunk_document_list


async def get_graph_document_list(
    llm, combined_chunk_document_list, allowedNodes, allowedRelationship
):
    futures = []
    graph_document_list = []
    if "diffbot_api_key" in dir(llm):
        llm_transformer = llm
    else:
        if "get_name" in dir(llm) and llm.get_name() != "ChatOenAI" or llm.get_name() != "ChatVertexAI" or llm.get_name() != "AzureChatOpenAI":
            node_properties = False
            relationship_properties = False
        else:
            node_properties = ["description"]
            relationship_properties = ["description"]
        llm_transformer = LLMGraphTransformer(
            llm=llm,
            node_properties=node_properties,
            relationship_properties=relationship_properties,
            allowed_nodes=allowedNodes,
            allowed_relationships=allowedRelationship,
            ignore_tool_usage=True,
            #prompt = ChatPromptTemplate.from_messages(["system",PROMPT_TO_ALL_LLMs])
        )
    # with ThreadPoolExecutor(max_workers=10) as executor:
    #     for chunk in combined_chunk_document_list:
    #         chunk_doc = Document(
    #             page_content=chunk.page_content.encode("utf-8"), metadata=chunk.metadata
    #         )
    #         futures.append(
    #             executor.submit(llm_transformer.convert_to_graph_documents, [chunk_doc])
    #         )

    #     for i, future in enumerate(concurrent.futures.as_completed(futures)):
    #         graph_document = future.result()
    #         graph_document_list.append(graph_document[0])
    
    if isinstance(llm,DiffbotGraphTransformer):
        graph_document_list = llm_transformer.convert_to_graph_documents(combined_chunk_document_list)
    else:
        graph_document_list = await llm_transformer.aconvert_to_graph_documents(combined_chunk_document_list)
    return graph_document_list


async def get_graph_from_llm(model, chunkId_chunkDoc_list, allowedNodes, allowedRelationship):
    
    llm, model_name = get_llm(model)
    combined_chunk_document_list = get_combined_chunks(chunkId_chunkDoc_list)
    
    if  allowedNodes is None or allowedNodes=="":
        allowedNodes =[]
    else:
        allowedNodes = allowedNodes.split(',')    
    if  allowedRelationship is None or allowedRelationship=="":   
        allowedRelationship=[]
    else:
        allowedRelationship = allowedRelationship.split(',')
        
    graph_document_list = await get_graph_document_list(
        llm, combined_chunk_document_list, allowedNodes, allowedRelationship
    )
    return graph_document_list
