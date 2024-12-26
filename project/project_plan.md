### SpeakCare MVP Development Plan

---

### Assumptions

#### Team Size and Outsourcing
1. **Core Team**:
   - 3 internal developers for critical backend services and workflows.
2. **Outsourced Team**:
   - **Browser Extension** and **Mobile / Smartwatch App** development.
   - **DevOps and Infrastructure as Code (IaC)** for cloud deployment.
   - **Logging and Monitoring setup.**
3. **UX/UI Design**:
   - Initial design for frontend (browser extension and mobile app) to be completed by Week 5.

#### Critical Priorities
1. **EHR Integration**: High priority and part of the MVP, timeline increased to **6 weeks** to reflect realistic estimates.
2. **HIPAA Compliance and Security**: Implemented throughout development, with a focus on secure deployment and monitoring.

#### Scope Adjustments and Simplifications
1. **Text Sanitization**: Minimal implementation; assume relevant periods are recorded.
2. **Patient Attribution**: Simplified, based on the nurse stating the patient's name at the start of conversations.
3. **Context Construction**: Deferred; assume well-defined recording periods with no interruptions.
4. **Clinical Documentation Conversion**: Simplified; use LLM-only without RAG, GraphRAG, or VectorDB.
5. **Workflow Orchestration and Cloud Deployment**: Added as foundational components.

---

## 1. Task Breakdown

### A. Define the Scope of the MVP
The MVP will deliver the following key functionalities:
1. **Audio Collection and Ingestion**:
   - Collect audio from the mobile app.
   - Perform noise reduction and segmentation.
   - Convert audio to text with speaker diarization.
2. **Simplified Data Processing**:
   - Perform minimal text sanitization.
   - Conduct basic patient attribution.
3. **Clinical Documentation Generation**:
   - Generate structured documents using LLM.
4. **Frontend Interfaces**:
   - Browser extension for reviewing and approving documents.
   - Mobile app for audio collection and notifications.
5. **EHR Integration**:
   - Fetch patient data (read service).
   - Submit approved documentation (write service).
6. **Centralized User Management**:
   - IDM for internal users.
   - OAuth 2.0 integration for external users (EHR authentication).
7. **Workflow Orchestration**:
   - Internal workflow management system to handle sequential service execution.
8. **Web Service**:
   - Serve browser extension and HITL apps.
9. **Data Stores**:
   - Support data processing stages.
10. **HITL Services**:
   - Enable internal teams to audit, correct, and provide feedback.
11. **Rule-Based Post-Processing**:
   - Placeholder rules for compliance and minimal enforcement.
12. **Knowledge Base**:
   - Database and CRUD functionalities for collecting compliance rules and other metadata.
13. **DevOps and HIPAA Compliance**:
   - Cloud deployment with monitoring and security practices.
   - Logging and monitoring for real-time insights and compliance tracking.
14. **Monitoring and Logging**:
   - Implement monitoring and logging for real-time tracking and compliance.

---

### B. System Deliverable Components Breakdown

#### Core Team Responsibilities
1. **Backend Services**:
   - Audio ingestion (noise reduction and segmentation).
   - Speech-to-text service.
   - Simplified data processing pipeline:
     - Minimal text sanitization.
     - Basic patient attribution.
   - Clinical Documentation Conversion (LLM-only).
   - Workflow orchestration.
   - HITL services.
   - Rule-Based Post-Processing (placeholder rules).
2. **EHR Integration**:
   - Read and write services for patient data and documents.
3. **Knowledge Base**:
   - Database and basic CRUD functionalities for rule collection.
4. **Web Service**:
   - Serve browser extension and HITL apps.
5. **Data Stores**:
   - Support data processing stages.
6. **Centralized User Management**:
   - System IDM and OAuth 2.0 integration.
7. **Testing and Debugging**:
   - Ensure HIPAA compliance and security.

#### Outsourced Responsibilities
1. **Frontend Development**:
   - Browser extension for document review and approval.
   - Mobile app for audio collection and notifications.
2. **DevOps**:
   - Cloud deployment with IaC (e.g., Terraform).
   - Logging and monitoring setup.
   - Security practices and monitoring.
3. **Monitoring and Logging**:
   - Implement logging and monitoring tools within 2 weeks.

---

### C. Tasks Prioritization Based on Dependencies

| **Priority**         | **Tasks**                                                                          |
|-----------------------|------------------------------------------------------------------------------------|
| **High Priority**     | Cloud deployment, workflow orchestration, audio ingestion, speech-to-text service, clinical documentation conversion (LLM). |
|                       | EHR integration (read/write services).                                            |
|                       | Web service (serve browser extension and HITL apps).                              |
|                       | Data stores (support different stages).                                           |
| **Medium Priority**   | HITL services.                                                                    |
|                       | Rule-based post-processing (placeholder rules).                                   |
| **Low Priority**      | Knowledge base (CRUD functionalities and rule collection).                        |
| **Supporting Task**   | Monitoring and logging.                                                           |

---

## 2. Estimated Timelines and Milestones

### A. Effort Estimates for Each Task (+Adjustments)

#### Adjustments
1. **Core Team Utilization**: Effort estimates for core team tasks are divided by 0.8 to reflect the 80% utilization factor.
2. **Project Buffer**: A 15% buffer is applied to the overall timeline after core and outsourced tasks are planned.

| **Component**                        | **Original Effort (Weeks)** | **Adjusted Effort (Weeks)** | **Team**         |
|--------------------------------------|-----------------------------|-----------------------------|------------------|
| **Mobile App**                       | 3                           | 3                           | Outsourced       |
| **Browser Extension**                | 3                           | 3                           | Outsourced       |
| **Audio Ingestion**                  | 3                           | 3.75                        | Core Team        |
| **Speech-to-Text Service**           | 3                           | 3.75                        | Core Team        |
| **Clinical Documentation Conversion**| 4                           | 5                           | Core Team        |
| **EHR Integration (Read/Write)**     | 6                           | 7.5                         | Core Team        |
| **Workflow Orchestration**           | 3                           | 3.75                        | Core Team        |
| **Web Service**                      | 3                           | 3.75                        | Core Team        |
| **Data Stores**                      | 3                           | 3.75                        | Core Team        |
| **HITL Services**                    | 3                           | 3.75                        | Core Team        |
| **Rule-Based Post-Processing**       | 2                           | 2.5                         | Core Team        |
| **Knowledge Base**                   | 3                           | 3.75                        | Core Team        |
| **DevOps and IaC**                   | 8                           | 10                          | Outsourced       |
| **Monitoring and Logging**           | 2                           | 2                           | Outsourced       |
| **Testing and Debugging**            | 4                           | 5                           | Core Team        |

---

### B. Milestones

#### Core Team Milestones (Adjusted with Utilization)

| **Milestone**                | **Tasks**                                                | **Adjusted Timeline** |
|------------------------------|---------------------------------------------------------|------------------------|
| **Milestone 1 (Weeks 1-5)**  | Cloud deployment, audio ingestion, speech-to-text service. | Weeks 1-5             |
| **Milestone 2 (Weeks 6-11)** | Clinical documentation, EHR integration, workflow orchestration. | Weeks 6-11            |
| **Milestone 3 (Weeks 12-16)**| Web service, data stores, centralized user management.   | Weeks 12-16           |
| **Milestone 4 (Weeks 17-21)**| HITL services, rule-based post-processing, testing.      | Weeks 17-21           |
| **Milestone 5 (Weeks 22-24)**| Knowledge base, final testing, HIPAA compliance, deployment. | Weeks 22-24           |

#### Outsourced Milestones

| **Milestone**                | **Tasks**                                                | **Timeline**       |
|------------------------------|---------------------------------------------------------|--------------------|
| **Milestone 1 (Weeks 1-4)**  | Initial DevOps Setup                                    | Weeks 1-4          |
| **Milestone 2 (Weeks 5-12)** | Browser Extension Development, DevOps Refinement       | Weeks 5-12         |
| **Milestone 3 (Weeks 9-16)** | Final DevOps, Testing for Frontend and Infrastructure   | Weeks 9-16         |
| **Milestone 4 (Weeks 17-19)**| Monitoring and Logging Setup                            | Weeks 17-19        |

---

### C. Timeline Proposal for MVP (With Buffer)

1. **Base Timeline**: 24 weeks (6 months).
2. **Project Buffer (15%)**: Adds ~3 weeks for unforeseen delays.
3. **Final Adjusted Timeline**: Overall MVP Completion in 27 weeks (6.5 months).

| **Phase**                     | **Tasks**                                      | **Adjusted Timeline** |
|-------------------------------|------------------------------------------------|------------------------|
| **Phase 1: Setup and Backend**| Cloud deployment, audio ingestion, speech-to-text, workflow orchestration. | Weeks 1-5             |
| **Phase 2: Processing**       | Clinical documentation, EHR integration        | Weeks 6-11            |
| **Phase 3: Frontend**         | Browser extension, centralized user management | Weeks 12-16           |
| **Phase 4: Enhancements**     | HITL services, rule-based post-processing      | Weeks 17-21           |
| **Phase 5: Final Testing**    | Knowledge base, compliance, deployment         | Weeks 22-27           |

---

