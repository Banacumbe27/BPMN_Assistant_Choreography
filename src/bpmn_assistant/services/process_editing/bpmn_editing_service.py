from copy import deepcopy

from bpmn_assistant.config import logger
from bpmn_assistant.core import EditProposal, IntermediateEditProposal, LLMFacade
from bpmn_assistant.core.exceptions import ElementNotFoundException, ProcessException
from bpmn_assistant.core.schemas import model_type
from bpmn_assistant.prompts import PromptTemplateProcessor
from bpmn_assistant.services.process_editing import (
    add_element,
    add_message_flow,
    add_participant,
    delete_element,
    delete_message_flow,
    delete_participant,
    move_element,
    redirect_branch,
    update_element,
)
from bpmn_assistant.services.process_editing.collaboration_functions import (
    COLLABORATION_FUNCTIONS,
)
from bpmn_assistant.services.validate_bpmn import validate_element, validate_model


class BpmnEditingService:
    def __init__(self, llm_facade: LLMFacade, process, change_request: str):
        self.llm_facade = llm_facade
        self.process = process
        self.change_request = change_request
        self.is_collaboration = model_type(process) == "collaboration"
        self.prompt_processor = PromptTemplateProcessor()

    def edit_bpmn(self) -> list:
        """
        Edit a BPMN process based on a change request.
        Returns:
            The updated BPMN process
        """
        updated_process = self._apply_initial_edit()
        updated_process = self._apply_intermediate_edits(updated_process)

        return updated_process

    def _apply_initial_edit(self, max_retries: int = 4) -> list:
        """
        Apply the initial edit to the process.
        Args:
            max_retries: The maximum number of retries to perform if the response is invalid
        Returns:
            The updated process
        """
        attempts = 0

        prompt = self.prompt_processor.render_template(
            "edit_bpmn.jinja2",
            process=str(self.process),
            change_request=self.change_request,
        )

        last_error: Exception | None = None

        while attempts < max_retries:
            attempts += 1

            # Get initial edit proposal
            try:
                edit_proposal: EditProposal = self.llm_facade.call(
                    prompt, structured_output=EditProposal
                )
                logger.info(f"Edit proposal: {edit_proposal}")
                self._validate_edit_proposal(edit_proposal)

                # Update process based on the edit proposal
                try:
                    updated_process = self._update_process(self.process, edit_proposal)
                    validate_model(updated_process)
                    return updated_process
                except (ProcessException, ValueError) as e:
                    last_error = e
                    logger.warning(f"Validation error (attempt {attempts}): {str(e)}")
                    prompt = f"Error: {str(e)}. Try again. Change request: {self.change_request}"
            except ValueError as e:
                last_error = e
                logger.warning(f"Validation error (attempt {attempts}): {str(e)}")
                prompt = f"Editing error: {str(e)}. Provide a new edit proposal."

        message = "Max number of retries reached."
        if last_error:
            message += f" Last error from provider: {last_error}"
        raise ValueError(message)

    def _apply_intermediate_edits(
        self,
        updated_process: list,
        max_retries: int = 4,
        max_num_of_iterations: int = 15,
    ) -> list:
        """
        Apply intermediate edits to the process.
        Args:
            updated_process: The updated process after the initial edit
            max_retries: The maximum number of retries to perform if the response is invalid
            max_num_of_iterations: The maximum number of iterations to perform
        Returns:
            The updated process
        Raises:
            Exception: If the max number of retries or iterations is reached
        """
        last_iteration_error: Exception | None = None

        for iteration_index in range(max_num_of_iterations):
            attempts = 0

            prompt = self.prompt_processor.render_template(
                "edit_bpmn_intermediate_step.jinja2",
                process=str(updated_process),
            )

            last_error: Exception | None = None

            while attempts < max_retries:
                attempts += 1

                try:
                    edit_proposal: IntermediateEditProposal = self.llm_facade.call(
                        prompt, structured_output=IntermediateEditProposal
                    )
                    logger.info(f"Intermediate edit proposal: {edit_proposal}")
                    self._validate_edit_proposal(edit_proposal, is_first_edit=False)

                    if "stop" in edit_proposal:
                        logger.info("Edit process stopped.")
                        return updated_process

                    updated_process = self._update_process(
                        updated_process, edit_proposal
                    )
                    validate_model(updated_process)

                    break

                except (ValueError, ProcessException) as e:
                    last_error = e
                    last_iteration_error = e
                    logger.warning(f"Validation error (attempt {attempts}): {str(e)}")
                    prompt = f"Editing error: {str(e)}. Provide a new edit proposal."

            else:
                error_message = (
                    f"Edit iteration {iteration_index+1} failed after {max_retries} attempts."
                )
                if last_error:
                    error_message += f" Last error from provider: {last_error}"
                raise ValueError(error_message)

        message = "Max number of editing iterations reached."
        if last_iteration_error:
            message += f" Last error from provider: {last_iteration_error}"
        raise ValueError(message)

    def _update_process(self, process, edit_proposal: dict):
        """
        Update the process based on the edit proposal.
        Args:
            process: The BPMN model to be edited (a process list, or a
                collaboration dict).
            edit_proposal: The edit proposal from the LLM (function and args)
        Returns:
            The updated model (same shape as the input)
        Raises:
            ProcessException: If the edit proposal is invalid
        """
        element_functions = {
            "delete_element": delete_element,
            "redirect_branch": redirect_branch,
            "add_element": add_element,
            "move_element": move_element,
            "update_element": update_element,
        }
        collaboration_functions = {
            "add_participant": add_participant,
            "delete_participant": delete_participant,
            "add_message_flow": add_message_flow,
            "delete_message_flow": delete_message_flow,
        }

        function_to_call = edit_proposal["function"]
        args = dict(edit_proposal["arguments"])

        # Collaboration-level edits operate on the whole model.
        if function_to_call in COLLABORATION_FUNCTIONS:
            if not self.is_collaboration:
                raise ValueError(
                    f"'{function_to_call}' is only valid when editing a collaboration."
                )
            res = collaboration_functions[function_to_call](process, **args)
            return res["process"]

        # Element-level edits. For a collaboration, they target one participant's
        # process (selected by 'participant_id'); for a single process they apply
        # directly.
        if self.is_collaboration:
            participant_id = args.pop("participant_id", None)
            participant_process, participant = self._resolve_participant(
                process, participant_id
            )
            res = element_functions[function_to_call](participant_process, **args)
            model_copy = deepcopy(process)
            for p in model_copy["participants"]:
                if p["id"] == participant["id"]:
                    p["process"] = res["process"]
                    break
            return model_copy

        res = element_functions[function_to_call](process, **args)
        return res["process"]

    def _resolve_participant(self, model: dict, participant_id):
        participants = model.get("participants", [])
        if participant_id is None:
            if len(participants) == 1:
                p = participants[0]
                return p.get("process", []), p
            raise ValueError(
                "Element edits on a collaboration require a 'participant_id' "
                "argument identifying which pool to edit."
            )
        for p in participants:
            if p["id"] == participant_id:
                return p.get("process", []), p
        raise ElementNotFoundException(
            f"Participant with id {participant_id} does not exist"
        )

    def _validate_edit_proposal(
        self, edit_proposal: dict, is_first_edit: bool = True
    ) -> None:
        """
        Validate the edit proposal from the LLM.
        Args:
            edit_proposal: The edit proposal from the LLM
            is_first_edit: Whether the response is for the initial edit
        Raises:
            ValueError: If the edit proposal is invalid
        """

        if not is_first_edit and "stop" in edit_proposal:
            if len(edit_proposal) > 1:
                raise ValueError(
                    "If 'stop' key is present, no other key should be provided."
                )
            return

        if "function" not in edit_proposal or "arguments" not in edit_proposal:
            raise ValueError(
                "Function call should contain 'function' and 'arguments' keys."
            )

        function_to_call = edit_proposal["function"]
        args = dict(edit_proposal["arguments"])

        # Collaboration-level edits
        if function_to_call in COLLABORATION_FUNCTIONS:
            if not self.is_collaboration:
                raise ValueError(
                    f"'{function_to_call}' is only valid when editing a collaboration."
                )
            self._validate_collaboration_op(function_to_call, args)
            return

        # For element edits on a collaboration, 'participant_id' selects the pool
        # and is not part of the underlying element-function signature.
        if self.is_collaboration:
            args.pop("participant_id", None)

        if function_to_call == "delete_element":
            self._validate_delete_element(args)
        elif function_to_call == "redirect_branch":
            self._validate_redirect_branch(args)
        elif function_to_call == "add_element":
            self._validate_add_element(args)
        elif function_to_call == "move_element":
            self._validate_move_element(args)
        elif function_to_call == "update_element":
            self._validate_update_element(args)
        else:
            raise ValueError(f"Function '{function_to_call}' not found.")

    def _validate_collaboration_op(self, function_to_call: str, args: dict) -> None:
        if function_to_call == "add_participant":
            if "participant" not in args:
                raise ValueError("Arguments should contain 'participant' key.")
        elif function_to_call == "delete_participant":
            if "participant_id" not in args:
                raise ValueError("Arguments should contain 'participant_id' key.")
        elif function_to_call == "add_message_flow":
            if "message_flow" not in args:
                raise ValueError("Arguments should contain 'message_flow' key.")
        elif function_to_call == "delete_message_flow":
            if "message_flow_id" not in args:
                raise ValueError("Arguments should contain 'message_flow_id' key.")

    def _validate_update_element(self, args):
        if "new_element" not in args:
            raise ValueError("Arguments should contain 'new_element' key.")
        elif len(args) > 1:
            raise ValueError("Arguments should contain only 'new_element' key.")
        validate_element(args["new_element"])

    def _validate_move_element(self, args):
        if "element_id" not in args:
            raise ValueError("Arguments should contain 'element_id' key.")
        elif "before_id" in args and "after_id" in args:
            raise ValueError(
                "Only one of 'before_id' and 'after_id' should be provided."
            )
        elif "before_id" not in args and "after_id" not in args:
            raise ValueError("Either 'before_id' or 'after_id' should be provided.")
        elif len(args) > 2:
            raise ValueError(
                "Arguments should contain only 'element_id' and either 'before_id' or 'after_id' keys."
            )

    def _validate_add_element(self, args):
        if "element" not in args:
            raise ValueError("Arguments should contain 'element' key.")
        elif "before_id" in args and "after_id" in args:
            raise ValueError(
                "Only one of 'before_id' and 'after_id' should be provided."
            )
        elif "before_id" not in args and "after_id" not in args:
            raise ValueError("Either 'before_id' or 'after_id' should be provided.")
        elif len(args) > 2:
            raise ValueError(
                "Arguments should contain only 'element' and either 'before_id' or 'after_id' keys."
            )
        validate_element(args["element"])

    def _validate_redirect_branch(self, args):
        if "branch_condition" not in args or "next_id" not in args:
            raise ValueError(
                "Arguments should contain 'branch_condition' and 'next_id' keys."
            )
        elif len(args) > 2:
            raise ValueError(
                "Arguments should contain only 'branch_condition' and 'next_id' keys."
            )

    def _validate_delete_element(self, args):
        if "element_id" not in args:
            raise ValueError("Arguments should contain 'element_id' key.")
        elif len(args) > 1:
            raise ValueError("Arguments should contain only 'element_id' key.")
