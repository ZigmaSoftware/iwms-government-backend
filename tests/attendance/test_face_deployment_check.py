from io import StringIO
from unittest.mock import Mock, patch

import pytest
from django.core.management import call_command, CommandError


@pytest.mark.parametrize("ready", [True, False])
def test_deployment_check_requires_a_ready_provider(ready):
    provider = Mock(name="provider")
    provider.name = "insightface"
    provider.health.return_value = (ready, None if ready else "libxcb.so.1 missing")
    output = StringIO()
    with patch("app.management.commands.check_face_recognition.get_provider", return_value=provider):
        if ready:
            call_command("check_face_recognition", stdout=output)
            assert "insightface ready" in output.getvalue()
        else:
            with pytest.raises(CommandError, match="libxcb.so.1 missing"):
                call_command("check_face_recognition", stdout=output)
