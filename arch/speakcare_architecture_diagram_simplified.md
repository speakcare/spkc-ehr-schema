```mermaid
flowchart TB
    %% User Interaction
    NurseUser["👩‍⚕️ Nurse User"] --> MobileApp["📱 Mobile App<br>(Audio Collector)"]
    NurseUser --> BrowserExt["💻 Browser Extension<br>(Document Review & Approval)"]

    %% Audio to Text Pipeline
    MobileApp --> AudioProcessing["🎧 Audio Processing"]
    AudioProcessing --> STT["🗣️ Speech-to-Text Service"]
    STT --> IntermediateStorage["📄 NoSQL Document DB"]

    %% Orchestrated Processing Pipeline
    IntermediateStorage --> WorkflowOrchestrator["🔗 Workflow Orchestrator"]
    WorkflowOrchestrator --> PatientAttribution["🔍 Patient Attribution"]
    PatientAttribution --> DataSanitation["🧹 Data Sanitation"]
    DataSanitation --> LLMProcessing["🤖 Clinical Documentation Conversion"]

    %% Data Enrichment via EHR
    EHRRead["📥 EHR Read Service"] --> PatientAttribution
    EHRRead --> DataSanitation
    EHRRead --> LLMProcessing

    %% Documentation Storage and Submission
    LLMProcessing --> CandidateDocs["📑 Candidate Documents"]
    CandidateDocs --> StructuredDB["🗂️ Structured DB (PostgreSQL)"]
    StructuredDB --> BrowserExt
    BrowserExt --> UserApproval["✅ User Approval"]

    %% EHR Submission
    UserApproval --> EHRWrite["📤 EHR Write Service"]
    EHRWrite --> EHRAPI["🛠️ EHR API"]

    %% Long-term Storage and Analytics
    StructuredDB --> DataLake["🌊 Data Lake<br>(Future AI/ML Analytics)"]
    IntermediateStorage --> DataLake

    %% Grouping for Clarity
    subgraph AudioTextPipeline["🎧 Audio to Text Pipeline"]
        AudioProcessing
        STT
    end

    subgraph EHRIntegration["🛠️ EHR Integration"]
        EHRRead
        EHRWrite
        EHRAPI
    end

    subgraph ProcessingPipeline["🔗 Orchestrated Processing"]
        PatientAttribution
        DataSanitation
        LLMProcessing
    end

    subgraph DataStorage["📊 Data Storage"]
        StructuredDB
        IntermediateStorage
        DataLake
    end
