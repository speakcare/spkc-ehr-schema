```mermaid
flowchart TB
    %% User Interaction
    NurseUser["👩‍⚕️ Nurse User"] --> MobileApp["📱 Mobile App<br>(Audio Collector)"]
    NurseUser --> BrowserExt["💻 Browser Extension<br>(Document Review & Approval)"]

    %% Data Processing Pipeline
    MobileApp --> AudioProcessing["🎛️ Audio Processing (Noise Reduction)"]
    AudioProcessing --> AudioStorage["🗄️ Audio Storage"]
    AudioStorage --> STT["🗣️ Speech-to-Text Service"]
    STT --> InitialSanitization["🧹 Initial Text Sanitization"]
    InitialSanitization --> PatientAttribution["🔍 Patient Attribution & Context Construction"]
    PatientAttribution --> PatientSanitization["🧹 Patient Data Sanitization"]
    PatientSanitization --> ClinicalDocs["📑 Clinical Documentation Conversion"]

    %% Clinical Documentation Conversion Details
    subgraph ClinicalDocsDetails["📑 Clinical Documentation Conversion Details"]
        ClinicalDocs --> LLMService["🤖 LLM"]
        LLMService --> RAG["📚 RAG (Retrieval-Augmented Generation)"]
        LLMService --> GraphRAG["🌐 GraphRAG"]
        LLMService --> VectorDB["🔎 Vector Database"]
    end

    %% EHR Integration
    ClinicalDocs --> CandidateDocs["📄 Candidate Documents"]
    CandidateDocs --> StructuredDB["🗂️ Relational Database (PostgreSQL)"]
    StructuredDB --> BrowserExt
    BrowserExt --> UserApproval["✅ User Approval"]
    UserApproval --> EHRWrite["📤 EHR Write Service"]
    EHRWrite --> EHRAPI["🛠️ EHR API"]
    EHRAPI --> StructuredDB

    %% Data Enrichment via EHR
    EHRRead["📥 EHR Read Service"] --> PatientAttribution
    EHRRead --> ClinicalDocs
    EHRRead --> LLMService

    %% Workflow Orchestrator
    WorkflowOrchestrator["🔗 Workflow Orchestrator"]
    WorkflowOrchestrator --> AudioProcessing
    WorkflowOrchestrator --> STT
    WorkflowOrchestrator --> InitialSanitization
    WorkflowOrchestrator --> PatientAttribution
    WorkflowOrchestrator --> PatientSanitization
    WorkflowOrchestrator --> ClinicalDocs

    %% Long-Term Storage and Analytics
    StructuredDB --> DataLake["🌊 Data Lake<br>(Future AI/ML Analytics)"]
    PatientSanitization --> DataLake

    %% Grouping for Clarity
    subgraph DataProcessingPipeline["🔗 Data Processing Pipeline"]
        AudioProcessing
        AudioStorage
        STT
        InitialSanitization
        PatientAttribution
        PatientSanitization
        ClinicalDocs
    end

    subgraph EHRIntegration["🛠️ EHR Integration"]
        EHRRead
        EHRWrite
        EHRAPI
    end

    subgraph DataStorage["📊 Data Storage"]
        StructuredDB
        DataLake
    end

    subgraph ClinicalDocsDetails["📑 Clinical Documentation Conversion Details"]
        LLMService
        RAG
        GraphRAG
        VectorDB
    end
