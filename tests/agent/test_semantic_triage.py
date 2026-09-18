"""Unit tests for the local semantic intent triage classifier."""

from agent.semantic_triage import SemanticIntentClassifier, classify_semantic_intent


def test_semantic_classifier_loads_weights():
    classifier = SemanticIntentClassifier.get_instance()
    assert classifier._coef is not None
    assert len(classifier._coef) == 384
    assert isinstance(classifier._intercept, float)
    assert classifier.is_available() is True


def test_semantic_classifier_conversational_cases():
    conversational_samples = [
        "Hola Roshi",
        "Buenos días",
        "¿Cómo estás?",
        "Ok perfecto, gracias",
        "Chau, hablamos luego",
        "Qué tal amigo",
        "Dale, entendido",
        "Muchas gracias por todo",
    ]
    for text in conversational_samples:
        assert (
            classify_semantic_intent(text) == "conversational"
        ), f"Expected '{text}' to be conversational"


def test_semantic_classifier_action_cases():
    action_samples = [
        "¿Cómo va el proceso?",
        "¿Cómo va la tarea?",
        "¿Cuáles son los avances?",
        "Revisa el informe de skills",
        "Ejecuta el script de validación",
        "Arregla la sesión con Roshi que se dañó",
        "Clasificar el destino de los cascarones del lote CH1",
        "Adelante",
        "¿Y ahora qué pasó? No me respondió mi última solicitud",
        "Hola, ¿cómo va el proceso?",
        "Buenas tardes, revisa los logs por favor",
    ]
    for text in action_samples:
        assert (
            classify_semantic_intent(text) == "action"
        ), f"Expected '{text}' to be action"


def test_semantic_classifier_fail_open_on_empty():
    assert classify_semantic_intent("") == "action"
    assert classify_semantic_intent("   ") == "action"
    assert classify_semantic_intent(None) == "action"
