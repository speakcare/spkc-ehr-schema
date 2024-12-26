```mermaid
flowchart TB
    %% User Interaction
    NurseUser["👩‍⚕️ Nurse User"] --> MobileApp["📱 Mobile App<br>(Audio Collector)"]
    NurseUser --> BrowserExt["💻 Browser Extension<br>(Document Review & Approval)"]
    SpeakCareStuff["👩🏽‍🦳 SpeakCare personnel"] --> HITLApp["Human-In-The-Loop Application"]

    %% User Applications
    subgraph UserApplications["👩🏽‍🔧 User Applications"]
        BrowserExt
        HITLApp
    end

    %% Data Processing Pipeline
    MobileApp --> AudioIngestionAndProcessing["🎛️ Audio Ingestion and Processing"]
    AudioIngestionAndProcessing .-> AudioStorage["🫙 Audio Object Store"]
    AudioIngestionAndProcessing --> STT["🗣️ Speech-to-Text Service"]
    STT .-> DocumentDB["📄 NoSQL DocumentDB"]
    STT --> InitialSanitization["🧹 Initial Text Sanitization"]
    InitialSanitization .-> DocumentDB
    InitialSanitization --> PatientAttribution["🔍 Patient Attribution & Context Construction"]
    PatientAttribution .-> DocumentDB
    PatientAttribution --> PatientSanitization["🧹 Patient Data Sanitization"]
    PatientSanitization .-> DocumentDB
    PatientSanitization --> ConversationSentimentAnalysis["😡 Conversation Sentiment Analysis"]
    ConversationSentimentAnalysis .-> DocumentDB
    ConversationSentimentAnalysis --> DocumentationConversion["📑 Documentation Conversion Service (LLM)"]
    DocumentationConversion .-> LLMService["🤖 LLM"]
    DocumentationConversion .-> DocumentDB
    DocumentationConversion --> RuleBasedProcessing["👮🏼 Rule Based Post Processing"]
    RuleBasedProcessing .-> RuleDB["Rules Database"]
    RuleBasedProcessing .-> DocumentDB
    RuleBasedProcessing --> CandidateDocs["📄 Candidate Documents"] 

    %% Knowledge Base Details
    subgraph KnowledgeBaseDetails["📖 Knowledge Base"]
        VectorDB["⌗ Vector Database (Embeddings)"]
        GraphDB["🔎 GraphDB"]
        RuleDB["Rules Database"]
    end


    %% Documentation Conversion Details
    subgraph DocsConversionDetails["📑 Documentation Conversion Details"]
        LLMService --> RAG["📚 RAG (Retrieval-Augmented Generation)"]
        RAG --> VectorDB
        LLMService --> GraphRAG["🌐 GraphRAG"]
        GraphRAG --> GraphDB
    end

    %% Data Enrichment via EHR
    PatientAttribution --> EHRRead["📥 EHR Read Service"]
    VectorDB --> EHRRead 
    GraphDB --> EHRRead


    %% User flow
    CandidateDocs --> StructuredDB["🗂️ Relational Database (PostgreSQL)"]
    BrowserExt .-> WebService["🌐 Web Application Service"]
    WebService .-> UserWebApp["User Web Application Service"]
    UserWebApp --> StructuredDB
    UserWebApp .->  EHRWrite["📤 EHR Write Service"]
    EHRWrite .-> EHRAPI["🛠️ EHR API"]
    HITLApp --> WebService
    EHRRead --> EHRAPI
    WebService .-> InternalUserService["SpeakCare Internal User Service"]


    %% Workflow Orchestrator
    WorkflowOrchestrator["🔗 Workflow Orchestrator"]
    WorkflowOrchestrator --> AudioIngestionAndProcessing
    WorkflowOrchestrator --> STT
    WorkflowOrchestrator --> InitialSanitization
    WorkflowOrchestrator --> PatientAttribution
    WorkflowOrchestrator --> PatientSanitization
    WorkflowOrchestrator --> ConversationSentimentAnalysis
    WorkflowOrchestrator --> DocumentationConversion
    WorkflowOrchestrator --> RuleBasedProcessing

    %% Long-Term Storage and Analytics
    StructuredDB --> DataLake["🌊 Data Lake<br>(Future AI/ML Analytics)"]
    DocumentDB --> DataLake

    %% Human In The Loop Flows
    InternalUserService .-> StructuredDB
    InternalUserService .-> DocumentDB

    %% Grouping for Clarity
    subgraph DataProcessingPipeline["🔗 Data Processing Pipeline"]
        AudioIngestionAndProcessing
        STT
        InitialSanitization
        PatientAttribution
        PatientSanitization
        ConversationSentimentAnalysis
        DocumentationConversion
        RuleBasedProcessing
        CandidateDocs
    end

    subgraph EHRIntegration["🛠️ EHR Integration"]
        EHRRead
        EHRWrite
        EHRAPI
    end

    subgraph DataStorage["📊 Data Storage"]
        StructuredDB
        DataLake
        AudioStorage
        DocumentDB

    end

    subgraph ClinicalDocsDetails["📑 Clinical Documentation Conversion Details"]
        LLMService
        RAG
        GraphRAG
        VectorDB
    end