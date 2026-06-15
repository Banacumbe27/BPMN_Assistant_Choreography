from fastapi import FastAPI
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.middleware.cors import CORSMiddleware

from bpmn_assistant.api.requests import (
    AvailableProvidersRequest,
    BpmnToJsonRequest,
    ConversationalRequest,
    DetermineIntentRequest,
    ModifyBpmnRequest,
)
from bpmn_assistant.core import handle_exceptions
from bpmn_assistant.core.enums import OutputMode
from bpmn_assistant.core.schemas import model_type
from bpmn_assistant.services import (
    BpmnJsonGenerator,
    BpmnLayoutGenerator,
    BpmnModelingService,
    BpmnXmlGenerator,
    ConversationalService,
    determine_diagram_type,
    determine_intent,
)
from bpmn_assistant.utils import (
    extract_images_from_message_history,
    get_available_providers,
    get_llm_facade,
)

ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "https://bpmn-frontend.onrender.com",
]


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

bpmn_modeling_service = BpmnModelingService()
bpmn_xml_generator = BpmnXmlGenerator()
bpmn_layout_generator = BpmnLayoutGenerator()


@app.get("/")
async def health_check():
    return {"status": "ok"}


@app.post("/bpmn_to_json")
@handle_exceptions
async def _bpmn_to_json(request: BpmnToJsonRequest) -> JSONResponse:
    """
    Convert the BPMN XML to its JSON representation
    """
    bpmn_json_generator = BpmnJsonGenerator()
    result = bpmn_json_generator.create_bpmn_json(request.bpmn_xml)
    return JSONResponse(content=result)


@app.post("/available_providers")
@handle_exceptions
async def _available_providers(request: AvailableProvidersRequest) -> JSONResponse:
    """
    Get the available LLM providers
    """
    providers = get_available_providers(api_keys=request.api_keys)
    return JSONResponse(content=providers)


@app.post("/determine_intent")
@handle_exceptions
async def _determine_intent(request: DetermineIntentRequest) -> JSONResponse:
    """
    Determine the intent of the user query
    """
    llm_facade = get_llm_facade(request.model, api_keys=request.api_keys)
    images = extract_images_from_message_history(request.message_history)
    intent = determine_intent(llm_facade, request.message_history, images=images)
    return JSONResponse(content=intent)


@app.post("/modify")
@handle_exceptions
async def _modify(request: ModifyBpmnRequest) -> JSONResponse:
    """
    Modify the BPMN process based on the user query. If the request does not contain a BPMN JSON,
    then create a new BPMN process. Otherwise, edit the existing BPMN process.
    """
    llm_facade = get_llm_facade(request.model, api_keys=request.api_keys)
    text_llm_facade = get_llm_facade(
        request.model, OutputMode.TEXT, api_keys=request.api_keys
    )
    images = extract_images_from_message_history(request.message_history)

    if request.process:
        process = bpmn_modeling_service.edit_bpmn(
            llm_facade,
            text_llm_facade,
            request.process,
            request.message_history,
            images=images,
        )
    else:
        # Classify the diagram type on a separate facade so the create facade's
        # message history stays clean. Choreography routes to a dedicated prompt;
        # process vs collaboration is self-selected by the create prompt.
        classifier_facade = get_llm_facade(request.model, api_keys=request.api_keys)
        diagram_type = determine_diagram_type(
            classifier_facade, request.message_history, images=images
        )["diagram_type"]
        process = bpmn_modeling_service.create_bpmn(
            llm_facade,
            request.message_history,
            images=images,
            diagram_type=diagram_type,
        )

    bpmn_xml_string = bpmn_xml_generator.create_bpmn_xml(process)

    # Collaborations and choreographies cannot be laid out by the JS
    # bpmn-auto-layout service, so we embed deterministic DI here. Single
    # processes are left without DI and laid out by the layout server as before.
    if model_type(process) in ("collaboration", "choreography"):
        bpmn_xml_string = bpmn_layout_generator.add_di(process, bpmn_xml_string)

    return JSONResponse(content={"bpmn_xml": bpmn_xml_string, "bpmn_json": process})


@app.post("/talk")
async def _talk(request: ConversationalRequest) -> StreamingResponse:
    conversational_service = ConversationalService(
        request.model, api_keys=request.api_keys
    )
    images = extract_images_from_message_history(request.message_history)

    if request.needs_to_be_final_comment:
        response_generator = conversational_service.make_final_comment(
            request.message_history, request.process, images=images
        )
    else:
        response_generator = conversational_service.respond_to_query(
            request.message_history, request.process, images=images
        )

    return StreamingResponse(response_generator)
