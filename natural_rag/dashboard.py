from __future__ import annotations

from dash import Dash, html, dcc, callback, Output, Input
import dash_bootstrap_components as dbc

from natural_rag.data import RAGAnswerAndEvals
from natural_rag.dataset import RAGDataset


def run_dashboard(
    dataset: RAGDataset,
    evals: dict[str, dict[int, RAGAnswerAndEvals]],
) -> None:
    pipeline_names = sorted(evals.keys())

    # collect question indices that have evals in at least one pipeline
    q_indices_with_evals = sorted({
        q_idx
        for pipe_evals in evals.values()
        for q_idx in pipe_evals
    })

    # pre-calculate scores: {(pipeline, q_idx): (actual, max_possible)}
    scores: dict[tuple[str, int], tuple[int, int]] = {}
    for pipe_name, pipe_evals in evals.items():
        for q_idx, entry in pipe_evals.items():
            checklist = dataset.questions[q_idx].eval_rules
            if entry.evals and entry.evals.checks and checklist:
                total = 0
                max_possible = 0
                for cid, res in entry.evals.checks.items():
                    if cid in checklist.checks:
                        s = checklist.checks[cid].score
                        if s > 0:
                            max_possible += s
                        if res.decision:
                            total += s
                total = max(total, 0)
                scores[(pipe_name, q_idx)] = (total, max_possible)

    app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

    app.layout = dbc.Container([
        dbc.Row([
            dbc.Col([
                dbc.Label("Pipeline"),
                dcc.Dropdown(
                    id="pipeline-select",
                    options=[{"label": p, "value": p} for p in pipeline_names],
                    value=pipeline_names[0] if pipeline_names else None,
                ),
            ], md=6),
            dbc.Col([
                dbc.Label("Question index"),
                dcc.Dropdown(
                    id="question-select",
                ),
            ], md=4),
        ], className="mb-4"),
        html.Hr(),
        html.Div(id="content"),
    ], fluid=True)

    @callback(
        Output("question-select", "options"),
        Output("question-select", "value"),
        Input("pipeline-select", "value"),
    )
    def update_question_options(pipeline: str | None):
        options = []
        for i in q_indices_with_evals:
            label = str(i)
            if pipeline and (pipeline, i) in scores:
                actual, maximum = scores[(pipeline, i)]
                label = f"{i} (score {actual}/{maximum})"
            options.append({"label": label, "value": i})
        first = q_indices_with_evals[0] if q_indices_with_evals else None
        return options, first

    @callback(
        Output("content", "children"),
        Input("pipeline-select", "value"),
        Input("question-select", "value"),
    )
    def update(pipeline: str | None, q_idx: int | None):
        if pipeline is None or q_idx is None:
            return html.P("Select a pipeline and question.")

        q_idx = int(q_idx)
        question = dataset.questions[q_idx]

        # --- left column: question card ---
        q_parts: list = [
            html.H5("Question"),
            html.P(question.text),
        ]
        if comment := question.metadata.pop("comment", None):
            q_parts.append(html.P(
                comment,
                className="text-muted fst-italic",
            ))
        if question.reference_answers:
            q_parts.append(html.H6("Reference answers"))
            q_parts.extend(
                dcc.Markdown(f"- {a}") for a in question.reference_answers
            )
        if question.relevant:
            q_parts.append(html.H6("Relevant sources"))
            for src in question.relevant:
                loc_str = ""
                # if src.loc:
                #     loc_str = f"  locs: {src.loc}"
                q_parts.append(html.P(f"doc: {src.doc_id}{loc_str}"))
        if question.metadata:
            q_parts.append(html.H6("Metadata"))
            q_parts.append(html.Pre(str(question.metadata)))

        question_card = dbc.Card(dbc.CardBody(q_parts), className="mb-3")

        # --- right column: answer + evals ---
        entry = evals.get(pipeline, {}).get(q_idx)
        if entry is None:
            right_content = dbc.Alert(
                f"No evaluation found for pipeline={pipeline!r}, question={q_idx}",
                color="warning",
            )
            return dbc.Row([
                dbc.Col(question_card, md=4),
                dbc.Col(right_content, md=8),
            ])

        a_parts: list = [html.H5("Answer")]
        if entry.prompt:
            a_parts.append(html.H6("Prompt"))
            a_parts.append(html.Pre(
                entry.prompt,
                style={"maxHeight": "300px", "overflow": "auto",
                       "whiteSpace": "pre-wrap"},
            ))
        a_parts.append(html.H6("Generated answer"))
        a_parts.append(dcc.Markdown(entry.answer))
        answer_card = dbc.Card(dbc.CardBody(a_parts), className="mb-3")

        # --- evals card ---
        if entry.evals and entry.evals.checks:
            checklist = question.eval_rules
            rows = []
            for check_id, result in entry.evals.checks.items():
                rule_text = ""
                score = ""
                if checklist and check_id in checklist.checks:
                    rule = checklist.checks[check_id]
                    rule_text = rule.check
                    score = str(rule.score)
                rule_cell_parts: list = [html.Span(rule_text)]
                if (checklist and check_id in checklist.checks
                        and checklist.checks[check_id].metadata.get("comment")):
                    rule_cell_parts.append(html.Br())
                    rule_cell_parts.append(html.Small(
                        checklist.checks[check_id].metadata["comment"],
                        className="text-muted fst-italic",
                    ))
                badge_color = "success" if result.decision else "danger"
                rows.append(html.Tr([
                    html.Td(check_id),
                    html.Td(rule_cell_parts),
                    html.Td(score),
                    html.Td(dbc.Badge(
                        "PASS" if result.decision else "FAIL",
                        color=badge_color,
                    )),
                    html.Td(result.confidence),
                    html.Td(result.reasoning,
                            style={"fontSize": "0.85em"}),
                ]))
            evals_table = dbc.Table([
                html.Thead(html.Tr([
                    html.Th("ID"), html.Th("Rule"), html.Th("Score"),
                    html.Th("Result"), html.Th("Confidence"),
                    html.Th("Reasoning"),
                ])),
                html.Tbody(rows),
            ], bordered=True, hover=True, size="sm")

            # use pre-calculated scores
            if (pipeline, q_idx) in scores:
                actual, maximum = scores[(pipeline, q_idx)]
                score_text = f"Score: {actual} / {maximum}"
            else:
                score_text = ""

            evals_card = dbc.Card(dbc.CardBody([
                html.H5("Evaluation checks"),
                html.P(score_text, className="fw-bold") if score_text else None,
                evals_table,
            ]), className="mb-3")
        else:
            evals_card = dbc.Alert("No evaluation checks for this question.", color="info")

        return dbc.Row([
            dbc.Col(question_card, md=4),
            dbc.Col([answer_card, evals_card], md=8),
        ])

    app.run(host='0.0.0.0', port=8051, debug=True)
