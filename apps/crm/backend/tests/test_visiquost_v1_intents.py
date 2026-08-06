"""New Jarvis intents added for VisiQuost 1.0."""


def test_how_are_you_pt(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "tudo bem?"}).json()
    assert r["intent"] == "how_are_you", r
    assert "local" in r["reply"].lower()


def test_who_are_you_en(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "who are you"}).json()
    assert r["intent"] == "who_are_you", r
    assert "jarvis" in r["reply"].lower()


def test_capabilities_pt(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "o que você pode fazer"}).json()
    assert r["intent"] == "capabilities", r


def test_typo_correction_oportunidades(auth_client):
    """Typo 'opotunidades' should still resolve to top_opportunities."""
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "top 5 opotunidades"}).json()
    assert r["intent"] == "top_opportunities", r
    # Marker of typo correction
    assert "entendi" in r["reply"].lower()


def test_typo_correction_shedule(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "shedule a meeting for tomorrow at 3pm"}).json()
    assert r["intent"] == "schedule_meeting", r


def test_fallback_suggests_similar_commands(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "quero ver a agenda"}).json()
    # Either the intent was matched by "agenda" (calendar) or the fallback suggests it
    assert "agenda" in r["reply"].lower() or "calend" in r["reply"].lower()


def test_thanks_intent(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "obrigado"}).json()
    assert r["intent"] == "thanks", r


def test_goodbye_intent(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "tchau"}).json()
    assert r["intent"] == "goodbye", r


def test_who_am_i_intent(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "who am I"}).json()
    assert r["intent"] == "who_am_i", r
    assert "@" in r["reply"]


def test_top_opportunities_intent(auth_client):
    auth_client.post("/api/v1/opportunities", json={"name": "Big Deal", "amount": 100000})
    auth_client.post("/api/v1/opportunities", json={"name": "Small Deal", "amount": 500})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "top 3 opportunities"}).json()
    assert r["intent"] == "top_opportunities", r
    assert "Big Deal" in r["reply"]


def test_top_opportunities_pt(auth_client):
    auth_client.post("/api/v1/opportunities", json={"name": "Grandinha", "amount": 5000})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "top 5 oportunidades"}).json()
    assert r["intent"] == "top_opportunities"
    assert "Grandinha" in r["reply"]


def test_revenue_by_stage_intent(auth_client):
    auth_client.post("/api/v1/opportunities", json={"name": "X", "amount": 1000})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "revenue by stage"}).json()
    assert r["intent"] == "revenue_by_stage"


def test_revenue_by_stage_pt(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "receita por estágio"}).json()
    assert r["intent"] == "revenue_by_stage"


def test_leads_by_status_intent(auth_client):
    auth_client.post("/api/v1/leads", json={"first_name": "L1"})
    auth_client.post("/api/v1/leads", json={"first_name": "L2"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "leads by status"}).json()
    assert r["intent"] == "leads_by_status"
    assert "new" in r["reply"].lower() or "2" in r["reply"]


def test_closing_this_month_en(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "opportunities closing this month"}).json()
    assert r["intent"] == "closing_this_month"


def test_closing_this_month_pt(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "oportunidades fechando este mês"}).json()
    assert r["intent"] == "closing_this_month"


def test_weekly_digest_en(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "weekly digest"}).json()
    assert r["intent"] == "weekly_digest"
    assert "Digest" in r["reply"]
    assert "7 days" in r["reply"]


def test_monthly_digest_en(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "monthly digest"}).json()
    assert r["intent"] == "weekly_digest"
    assert "monthly" in r["reply"].lower() or "30 days" in r["reply"]


def test_monthly_digest_pt(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "resumo mensal detalhado"}).json()
    assert r["intent"] == "weekly_digest"
    assert "mensal" in r["reply"].lower() or "30 dias" in r["reply"]


def test_weekly_digest_pt(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "resumo semanal detalhado"}).json()
    assert r["intent"] == "weekly_digest"
    assert "Digest" in r["reply"]


def test_stale_leads_en(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "stale leads"}).json()
    assert r["intent"] == "stale_leads"


def test_stale_leads_pt(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "leads parados"}).json()
    assert r["intent"] == "stale_leads"


def test_read_calendar_empty(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "minha agenda"}).json()
    assert r["intent"] == "read_calendar", r
    # Local-only calendar: either "no events" hint or points at ICS local path
    assert "evento" in r["reply"].lower() or ".ics" in r["reply"].lower() or "nenhum" in r["reply"].lower()


def test_batch_vcard_export(auth_client):
    auth_client.post("/api/v1/contacts", json={"first_name": "A", "email": "a@x.com"})
    auth_client.post("/api/v1/contacts", json={"first_name": "B", "email": "b@x.com"})
    r = auth_client.get("/api/v1/contacts/vcards.vcf")
    assert r.status_code == 200
    assert "text/vcard" in r.headers["content-type"]
    body = r.text
    # Should have at least 2 vcards
    assert body.count("BEGIN:VCARD") >= 2
    assert body.count("END:VCARD") >= 2


def test_help_me_focus(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "help me focus"}).json()
    assert r["intent"] == "help_me_focus", r


def test_help_me_focus_with_seeded_data(auth_client):
    """Regression: crashed on populated workspace comparing datetime to date."""
    auth_client.post("/api/v1/workspaces/current/seed-demo")
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "help me focus"}).json()
    assert r["intent"] == "help_me_focus", r
    # Should not crash


def test_who_to_call_today_with_seeded_data(auth_client):
    """Same regression via who_to_call_today directly."""
    auth_client.post("/api/v1/workspaces/current/seed-demo")
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "who should I call today"}).json()
    assert r["intent"] == "who_to_call_today", r


def test_help_me_focus_pt(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "ajude a focar"}).json()
    assert r["intent"] == "help_me_focus", r


def test_daily_briefing_en(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "briefing"}).json()
    assert r["intent"] == "daily_briefing", r
    assert "briefing" in r["reply"].lower()


def test_daily_briefing_pt(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "meu dia"}).json()
    assert r["intent"] == "daily_briefing", r


def test_daily_briefing_whats_my_day(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "what's my day"}).json()
    assert r["intent"] == "daily_briefing", r


def test_who_to_call_today_empty(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "quem devo ligar hoje"}).json()
    assert r["intent"] == "who_to_call_today", r


def test_who_to_call_today_with_hot_lead(auth_client):
    auth_client.post("/api/v1/leads", json={"first_name": "HotHot", "score": 90, "status": "qualified"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "who should i call today"}).json()
    assert r["intent"] == "who_to_call_today", r
    # New lead with no activity → is included (999d cold)
    assert "HotHot" in r["reply"] or "priorit" in r["reply"].lower()


def test_top_companies_by_opps(auth_client):
    co = auth_client.post("/api/v1/companies", json={"name": "OppCorp"}).json()
    contact = auth_client.post("/api/v1/contacts", json={"first_name": "X", "company_id": co["id"]}).json()
    auth_client.post("/api/v1/opportunities", json={"name": "Big", "amount": 100000, "contact_id": contact["id"]})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "top empresas por valor"}).json()
    assert r["intent"] == "top_companies_by_opps", r
    assert "OppCorp" in r["reply"]


def test_orphan_contacts_pt(auth_client):
    auth_client.post("/api/v1/contacts", json={"first_name": "SoloContact"})
    linked_co = auth_client.post("/api/v1/companies", json={"name": "ExtraCorp"}).json()
    auth_client.post("/api/v1/contacts", json={"first_name": "LinkedContact", "company_id": linked_co["id"]})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "contatos sem empresa"}).json()
    assert r["intent"] == "orphan_contacts", r
    assert "SoloContact" in r["reply"]


def test_orphan_companies_pt(auth_client):
    orphan = auth_client.post("/api/v1/companies", json={"name": "OrphanCorp"}).json()
    linked = auth_client.post("/api/v1/companies", json={"name": "LinkedCorp"}).json()
    auth_client.post("/api/v1/contacts", json={"first_name": "Someone", "company_id": linked["id"]})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "empresas sem contatos"}).json()
    assert r["intent"] == "orphan_companies", r
    assert "OrphanCorp" in r["reply"]
    assert "LinkedCorp" not in r["reply"]


def test_orphan_companies_all_have_contacts(auth_client):
    co = auth_client.post("/api/v1/companies", json={"name": "AllLinked"}).json()
    auth_client.post("/api/v1/contacts", json={"first_name": "X", "company_id": co["id"]})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "orphan companies"}).json()
    assert r["intent"] == "orphan_companies"
    # Should say "all have contacts" OR list existing orphans from other tests
    # Just verify intent classified


def test_top_lead_sources_pt(auth_client):
    for src in ["LinkedIn", "LinkedIn", "Google", "Referral"]:
        auth_client.post("/api/v1/leads", json={"first_name": f"L_{src}", "source": src, "score": 20})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "top fontes de leads"}).json()
    assert r["intent"] == "top_lead_sources", r
    assert "LinkedIn" in r["reply"]
    # LinkedIn (2) should appear before Google (1)
    linkedin_pos = r["reply"].find("LinkedIn")
    google_pos = r["reply"].find("Google")
    assert linkedin_pos < google_pos


def test_top_lead_sources_en(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "top lead sources"}).json()
    assert r["intent"] == "top_lead_sources"


def test_brief_company_en(auth_client):
    auth_client.post("/api/v1/companies", json={"name": "MegaCorp", "domain": "megacorp.io", "industry": "SaaS"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "brief company MegaCorp"}).json()
    assert r["intent"] == "brief_company", r
    assert "MegaCorp" in r["reply"]
    assert "SaaS" in r["reply"]


def test_brief_lead_en(auth_client):
    auth_client.post("/api/v1/leads", json={"first_name": "Lucas", "score": 75, "company_name": "TechInc"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "brief lead Lucas"}).json()
    assert r["intent"] == "brief_lead", r
    assert "Lucas" in r["reply"]
    assert "75" in r["reply"]


def test_brief_opp_en(auth_client):
    auth_client.post("/api/v1/opportunities", json={
        "name": "BriefDeal", "amount": 50000, "probability": 60,
    })
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "brief opp BriefDeal"}).json()
    assert r["intent"] == "brief_opp", r
    assert "BriefDeal" in r["reply"]
    assert "50" in r["reply"]  # amount
    assert "Next step" in r["reply"] or "próximo passo" in r["reply"].lower()


def test_brief_opp_pt(auth_client):
    auth_client.post("/api/v1/opportunities", json={"name": "Neg PT", "amount": 1000})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "resumo oportunidade Neg PT"}).json()
    assert r["intent"] == "brief_opp"


def test_brief_opp_not_found(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "brief opp ZZZZZzzz-nonexistent"}).json()
    assert r["intent"] == "brief_opp"
    assert "não" in r["reply"].lower() or "no opportunity" in r["reply"].lower()


def test_monthly_forecast_endpoint(auth_client):
    from datetime import datetime, timedelta, timezone
    future = (datetime.now(timezone.utc) + timedelta(days=15)).date().isoformat()
    auth_client.post("/api/v1/opportunities", json={
        "name": "MonthlyDeal", "amount": 10000, "probability": 40,
        "expected_close_date": future,
    })
    r = auth_client.get("/api/v1/jarvis/monthly-forecast?months=6").json()
    assert r["months"] == 6
    assert len(r["buckets"]) == 6
    # At least one bucket should have our deal
    non_zero = [b for b in r["buckets"] if b["count"] > 0]
    assert len(non_zero) >= 1
    assert non_zero[0]["weighted"] == 4000.0  # 10000 * 40%


def test_contact_vcard_export(auth_client):
    c = auth_client.post("/api/v1/contacts", json={
        "first_name": "Grace", "last_name": "Hopper", "email": "grace@nebula.io",
        "phone": "+15551234567", "job_title": "VP Engineering",
    }).json()
    r = auth_client.get(f"/api/v1/contacts/{c['id']}/vcard")
    assert r.status_code == 200
    assert "text/vcard" in r.headers["content-type"]
    body = r.text
    assert "BEGIN:VCARD" in body
    assert "FN:Grace Hopper" in body
    assert "grace@nebula.io" in body
    assert "END:VCARD" in body


def test_read_file_http_endpoint(auth_client, monkeypatch, tmp_path):
    from app.jarvis import device_tools
    monkeypatch.setattr(device_tools, "_get_work_dir", lambda: tmp_path)
    (tmp_path / "sample.md").write_text("# Hello\nThis is a sample.", encoding="utf-8")
    r = auth_client.get("/api/v1/jarvis/read-file?filename=sample.md").json()
    assert r["status"] == "ok"
    assert "Hello" in r["text"]


def test_read_file_http_endpoint_not_found(auth_client, monkeypatch, tmp_path):
    from app.jarvis import device_tools
    monkeypatch.setattr(device_tools, "_get_work_dir", lambda: tmp_path)
    r = auth_client.get("/api/v1/jarvis/read-file?filename=nope.txt").json()
    assert r["error"] == "not_found"


def test_export_conversation_markdown(auth_client):
    chat = auth_client.post("/api/v1/jarvis/chat", json={"message": "unique-content-for-export"}).json()
    r = auth_client.get(f"/api/v1/jarvis/conversations/{chat['conversation_id']}/export.md")
    assert r.status_code == 200
    assert "text/markdown" in r.headers["content-type"]
    body = r.text
    assert body.startswith("# ")
    assert "unique-content-for-export" in body


def test_message_search_finds_by_content(auth_client):
    auth_client.post("/api/v1/jarvis/chat", json={"message": "some very unique zorlkbargle content"})
    r = auth_client.get("/api/v1/jarvis/messages/search?q=zorlkbargle").json()
    assert r["count"] >= 1
    assert "zorlkbargle" in r["hits"][0]["snippet"].lower()


def test_message_search_isolates_by_user(auth_client):
    """Sanity: search only within own conversations — this test just checks it doesn't crash."""
    r = auth_client.get("/api/v1/jarvis/messages/search?q=nada").json()
    assert "count" in r


def test_rename_conversation(auth_client):
    # First, spawn a conversation via /jarvis/chat
    chat = auth_client.post("/api/v1/jarvis/chat", json={"message": "hello"}).json()
    conv_id = chat["conversation_id"]
    r = auth_client.patch(f"/api/v1/jarvis/conversations/{conv_id}", json={"title": "My Chat"})
    assert r.status_code == 200
    assert r.json()["title"] == "My Chat"


def test_rename_conversation_empty_rejected(auth_client):
    chat = auth_client.post("/api/v1/jarvis/chat", json={"message": "test"}).json()
    conv_id = chat["conversation_id"]
    r = auth_client.patch(f"/api/v1/jarvis/conversations/{conv_id}", json={"title": ""})
    assert r.status_code == 422


def test_file_upload_ok(auth_client, monkeypatch, tmp_path):
    from app.jarvis import device_tools
    monkeypatch.setattr(device_tools, "_get_work_dir", lambda: tmp_path)
    r = auth_client.post(
        "/api/v1/files/upload",
        files={"file": ("hello.txt", b"hello world", "text/plain")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["name"] == "hello.txt"
    assert body["size"] == 11
    assert (tmp_path / "hello.txt").exists()


def test_file_upload_extension_blocked(auth_client, monkeypatch, tmp_path):
    from app.jarvis import device_tools
    monkeypatch.setattr(device_tools, "_get_work_dir", lambda: tmp_path)
    r = auth_client.post(
        "/api/v1/files/upload",
        files={"file": ("evil.exe", b"MZ...", "application/octet-stream")},
    )
    assert r.status_code == 400


def test_file_upload_dedupe(auth_client, monkeypatch, tmp_path):
    from app.jarvis import device_tools
    monkeypatch.setattr(device_tools, "_get_work_dir", lambda: tmp_path)
    auth_client.post("/api/v1/files/upload", files={"file": ("dup.csv", b"a", "text/csv")})
    r = auth_client.post("/api/v1/files/upload", files={"file": ("dup.csv", b"b", "text/csv")})
    assert r.status_code == 200
    assert r.json()["name"] == "dup (1).csv"


def test_workflow_templates_list(auth_client):
    r = auth_client.get("/api/v1/workflows/templates").json()
    keys = [t["key"] for t in r["templates"]]
    assert "hot_lead_task" in keys
    assert "opp_won_note" in keys


def test_workflow_install_from_template(auth_client):
    r = auth_client.post("/api/v1/workflows/from-template/hot_lead_task").json()
    assert r["name"] == "Follow-up automático em lead quente"
    assert r["is_active"] is True
    assert len(r["steps"]) == 1


def test_workflow_from_template_404(auth_client):
    r = auth_client.post("/api/v1/workflows/from-template/potato")
    assert r.status_code == 404


def test_email_templates_list(auth_client):
    r = auth_client.get("/api/v1/email-templates").json()
    keys = [t["key"] for t in r["templates"]]
    assert "cold_intro_pt" in keys
    assert "follow_up_en" in keys


def test_email_template_render_with_contact(auth_client):
    c = auth_client.post("/api/v1/contacts", json={"first_name": "Ada", "email": "ada@ex.com"}).json()
    r = auth_client.get(f"/api/v1/email-templates/cold_intro_pt/render?contact_id={c['id']}").json()
    assert "Ada" in r["rendered"]["body"]
    assert r["rendered"]["subject"].startswith("Oi Ada")


def test_email_template_render_with_freeform(auth_client):
    r = auth_client.get("/api/v1/email-templates/cold_intro_en/render?first_name=Grace&company=Nebula").json()
    assert "Grace" in r["rendered"]["body"]
    assert "Nebula" in r["rendered"]["subject"]


def test_email_template_404(auth_client):
    r = auth_client.get("/api/v1/email-templates/potato/render")
    assert r.status_code == 404


def test_find_duplicates_by_email(auth_client):
    auth_client.post("/api/v1/contacts", json={"first_name": "Dup", "email": "dup@ex.com"})
    r = auth_client.get("/api/v1/contacts/find-duplicates?email=dup@ex.com").json()
    assert len(r["matches"]) == 1
    assert r["matches"][0]["email"] == "dup@ex.com"
    assert r["matches"][0]["reason"] == "email"


def test_find_duplicates_by_name(auth_client):
    auth_client.post("/api/v1/contacts", json={"first_name": "Ada", "last_name": "Byte"})
    r = auth_client.get("/api/v1/contacts/find-duplicates?first_name=Ada&last_name=Byte").json()
    assert len(r["matches"]) == 1


def test_find_duplicates_empty_query(auth_client):
    r = auth_client.get("/api/v1/contacts/find-duplicates").json()
    assert r["matches"] == []


def test_pipeline_templates_list(auth_client):
    r = auth_client.get("/api/v1/pipelines/templates").json()
    keys = [t["key"] for t in r["templates"]]
    assert "saas" in keys
    assert "consulting" in keys


def test_install_pipeline_from_template(auth_client):
    r = auth_client.post("/api/v1/pipelines/from-template/saas").json()
    assert r["name"] == "SaaS B2B"
    assert len(r["stages"]) == 6
    won = [s for s in r["stages"] if s["is_won"]]
    assert len(won) == 1


def test_pipeline_from_unknown_template_404(auth_client):
    r = auth_client.post("/api/v1/pipelines/from-template/potato")
    assert r.status_code == 404


def test_read_local_file_txt(auth_client, monkeypatch, tmp_path):
    from app.jarvis import device_tools
    monkeypatch.setattr(device_tools, "_get_work_dir", lambda: tmp_path)
    (tmp_path / "notes.txt").write_text("hello from a local file", encoding="utf-8")
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "leia arquivo notes.txt"}).json()
    assert r["intent"] == "read_local_file", r
    assert "hello from a local file" in r["reply"]


def test_read_local_file_not_found(auth_client, monkeypatch, tmp_path):
    from app.jarvis import device_tools
    monkeypatch.setattr(device_tools, "_get_work_dir", lambda: tmp_path)
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "read file zzz.txt"}).json()
    assert r["intent"] == "read_local_file"
    assert "not found" in r["reply"].lower() or "não encontrei" in r["reply"].lower()


def test_read_local_file_path_escape_blocked(auth_client, monkeypatch, tmp_path):
    from app.jarvis import device_tools
    monkeypatch.setattr(device_tools, "_get_work_dir", lambda: tmp_path)
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "read file ../secret.txt"}).json()
    assert r["intent"] == "read_local_file"
    # Should not crash; should refuse or say not found
    assert "path" in r["reply"].lower() or "not found" in r["reply"].lower() or "escape" in r["reply"].lower() or "não" in r["reply"].lower()


def test_auto_import_endpoint_preview_and_commit(auth_client, monkeypatch, tmp_path):
    """HTTP endpoint for the 'Auto import' UI button."""
    from app.jarvis import device_tools
    monkeypatch.setattr(device_tools, "_get_work_dir", lambda: tmp_path)
    (tmp_path / "team.csv").write_text("first_name,email\nRosa,rosa@ex.com\n", encoding="utf-8")
    preview = auth_client.post("/api/v1/jarvis/auto-import-contacts").json()
    assert preview["status"] == "preview"
    assert preview["would_import"] == 1
    committed = auth_client.post("/api/v1/jarvis/auto-import-contacts?confirm=true").json()
    assert committed["status"] == "ok"
    assert committed["created"] == 1


def test_auto_import_contacts_preview_and_commit(auth_client, monkeypatch, tmp_path):
    from app.jarvis import device_tools
    monkeypatch.setattr(device_tools, "_get_work_dir", lambda: tmp_path)
    (tmp_path / "team.csv").write_text("first_name,last_name,email\nAda,Byte,ada@nebula.io\nGrace,Hop,grace@nebula.io\n", encoding="utf-8")
    (tmp_path / "family.vcf").write_text(
        "BEGIN:VCARD\nVERSION:3.0\nFN:Ken Thomson\nEMAIL:ken@unix.org\nTEL:+1234567890\nEND:VCARD\n",
        encoding="utf-8"
    )
    # Preview
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "importe contatos"}).json()
    assert r["intent"] == "auto_import_contacts", r
    assert "3" in r["reply"] or "found" in r["reply"].lower() or "encontrei" in r["reply"].lower()
    # Confirm
    r2 = auth_client.post("/api/v1/jarvis/chat", json={"message": "importe contatos confirme"}).json()
    assert r2["intent"] == "auto_import_contacts"
    assert "3" in r2["reply"] or "importados" in r2["reply"].lower() or "imported" in r2["reply"].lower()
    # Verify they exist
    contacts = auth_client.get("/api/v1/contacts?limit=50").json()
    names = {c["first_name"] for c in contacts["items"]}
    assert {"Ada", "Grace", "Ken"} <= names, names


def test_scan_work_dir_intent_pt(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "meus arquivos"}).json()
    assert r["intent"] == "scan_work_dir", r
    # Reply can be empty-hint or listing — accept any Portuguese marker
    body = r["reply"].lower()
    assert any(k in body for k in ["pasta", "arquivos", "vazia", "contatos", "agendas", "docs", "📂"])


def test_scan_work_dir_intent_en(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "what files do I have"}).json()
    assert r["intent"] == "scan_work_dir", r


def test_scan_work_dir_endpoint(auth_client):
    r = auth_client.get("/api/v1/jarvis/scan-work-dir")
    assert r.status_code == 200
    body = r.json()
    assert "status" in body


def test_read_calendar_from_local_ics(auth_client, monkeypatch, tmp_path):
    """Primary path: read events from a .ics file in the work dir."""
    from app.jarvis import device_tools
    ics = tmp_path / "test.ics"
    from datetime import datetime, timedelta, timezone
    future = datetime.now(timezone.utc) + timedelta(days=2)
    ics.write_text(
        "BEGIN:VCALENDAR\nVERSION:2.0\n"
        "BEGIN:VEVENT\n"
        "UID:1\n"
        f"DTSTART:{future.strftime('%Y%m%dT%H%M%SZ')}\n"
        f"DTEND:{(future + timedelta(hours=1)).strftime('%Y%m%dT%H%M%SZ')}\n"
        "SUMMARY:Local Standup\n"
        "LOCATION:Zoom\n"
        "END:VEVENT\nEND:VCALENDAR\n"
    )
    monkeypatch.setattr(device_tools, "_get_work_dir", lambda: tmp_path)
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "minha agenda"}).json()
    assert r["intent"] == "read_calendar", r
    assert "Local Standup" in r["reply"]


def test_close_stale_opportunities_en(auth_client):
    """No opps → 0 closed."""
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "close stale opportunities 30 days"}).json()
    assert r["intent"] == "close_stale_opportunities", r
    assert "0" in r["reply"] or "stale" in r["reply"].lower()


def test_close_stale_opportunities_pt(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "feche oportunidades paradas 45 dias"}).json()
    assert r["intent"] == "close_stale_opportunities"


def test_plan_week_en(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "plan my week"}).json()
    assert r["intent"] == "plan_week", r
    assert "focus" in r["reply"].lower() or "plan" in r["reply"].lower() or "pipeline" in r["reply"].lower()


def test_plan_week_pt(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "planeje minha semana"}).json()
    assert r["intent"] == "plan_week"
    assert "foco" in r["reply"].lower() or "plano" in r["reply"].lower()


def test_wins_losses_trend_endpoint(auth_client):
    r = auth_client.get("/api/v1/jarvis/wins-losses-trend?days=30").json()
    assert r["days"] == 30
    assert len(r["series"]) == 30
    assert "won" in r["totals"] and "lost" in r["totals"]


def test_workspace_summary_markdown(auth_client):
    r = auth_client.get("/api/v1/jarvis/workspace-summary.md")
    assert r.status_code == 200
    assert "text/markdown" in r.headers["content-type"]
    body = r.text
    assert body.startswith("# ")
    assert "Contadores" in body


def test_workspace_summary_markdown_with_data(auth_client):
    """Regression: crashed on populated workspaces because snap items are dicts."""
    # Populate at least one meeting, task, opportunity
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    auth_client.post("/api/v1/tasks", json={"title": "Overdue Test", "due_at": (now - timedelta(days=1)).isoformat().replace("+00:00", "Z")})
    auth_client.post("/api/v1/meetings", json={
        "title": "Upcoming Test",
        "starts_at": (now + timedelta(hours=6)).isoformat().replace("+00:00", "Z"),
        "ends_at": (now + timedelta(hours=7)).isoformat().replace("+00:00", "Z"),
    })
    auth_client.post("/api/v1/opportunities", json={"name": "OpenDeal", "amount": 999})
    r = auth_client.get("/api/v1/jarvis/workspace-summary.md")
    assert r.status_code == 200
    body = r.text
    assert "Overdue Test" in body
    assert "Upcoming Test" in body
    assert "OpenDeal" in body


def test_snooze_task_en(auth_client):
    t = auth_client.post("/api/v1/tasks", json={"title": "Snoozeable A"}).json()
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "snooze task Snoozeable for 3 days"}).json()
    assert r["intent"] == "snooze_task", r
    # Verify due_at was set forward
    updated = auth_client.get(f"/api/v1/tasks/{t['id']}").json()
    assert updated["due_at"] is not None


def test_snooze_task_pt(auth_client):
    t = auth_client.post("/api/v1/tasks", json={"title": "SnoozeMe PT"}).json()
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "adie a tarefa SnoozeMe por 5 dias"}).json()
    assert r["intent"] == "snooze_task", r
    updated = auth_client.get(f"/api/v1/tasks/{t['id']}").json()
    assert updated["due_at"] is not None


def test_restore_after_delete_contact(auth_client):
    c = auth_client.post("/api/v1/contacts", json={"first_name": "Undoable"}).json()
    cid = c["id"]
    # Soft-delete
    auth_client.delete(f"/api/v1/contacts/{cid}")
    # Restore
    r = auth_client.post(f"/api/v1/restore/contact/{cid}")
    assert r.status_code == 200
    assert r.json()["status"] == "restored"
    # Verify it's back in the list
    g = auth_client.get(f"/api/v1/contacts/{cid}")
    assert g.status_code == 200


def test_restore_unknown_kind_rejected(auth_client):
    from uuid import uuid4
    r = auth_client.post(f"/api/v1/restore/potato/{uuid4()}")
    assert r.status_code == 400


def test_delete_contact_by_name(auth_client):
    auth_client.post("/api/v1/contacts", json={"first_name": "Zaphod", "last_name": "Beeblebrox"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "delete contact Zaphod"}).json()
    assert r["intent"] == "delete_contact", r
    assert "🗑" in r["reply"] or "deleted" in r["reply"].lower()


def test_delete_company_pt(auth_client):
    auth_client.post("/api/v1/companies", json={"name": "OldCo"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "apague a empresa OldCo"}).json()
    assert r["intent"] == "delete_company"


def test_delete_opportunity(auth_client):
    auth_client.post("/api/v1/opportunities", json={"name": "DeadDeal"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "delete opportunity DeadDeal"}).json()
    assert r["intent"] == "delete_opportunity"


def test_delete_task_by_title(auth_client):
    auth_client.post("/api/v1/tasks", json={"title": "DeleteMe target task"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "delete task DeleteMe"}).json()
    assert r["intent"] == "delete_task", r
    assert "🗑" in r["reply"] or "deleted" in r["reply"].lower()


def test_delete_task_not_found(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "delete task ZorglkyNoExist"}).json()
    assert r["intent"] == "delete_task"
    assert "não" in r["reply"].lower() or "no task" in r["reply"].lower()


def test_mark_opportunity_won(auth_client):
    auth_client.post("/api/v1/opportunities", json={"name": "BigDeal Alpha", "amount": 5000})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "mark opportunity BigDeal as won"}).json()
    assert r["intent"] == "mark_opportunity", r
    assert "🏆" in r["reply"] or "won" in r["reply"].lower()


def test_mark_opportunity_lost_pt(auth_client):
    auth_client.post("/api/v1/opportunities", json={"name": "FailDeal", "amount": 100})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "marque a oportunidade FailDeal como perdida"}).json()
    assert r["intent"] == "mark_opportunity", r


def test_create_task_parses_priority_and_due(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={
        "message": "create task: call John tomorrow high",
    }).json()
    assert r["intent"] == "create_task", r
    # Task should have parsed priority=high and due_at set — verify by listing tasks
    tasks = auth_client.get("/api/v1/tasks?limit=10").json()
    call_john = next((t for t in tasks["items"] if "John" in t["title"] or "call" in t["title"].lower()), None)
    assert call_john is not None
    assert call_john["priority"] == "high", call_john
    assert call_john["due_at"] is not None, call_john


def test_create_task_links_contact_with_name(auth_client):
    auth_client.post("/api/v1/contacts", json={"first_name": "Zara"})
    r = auth_client.post("/api/v1/jarvis/chat", json={
        "message": "crie tarefa: follow-up com Zara amanhã",
    }).json()
    assert r["intent"] == "create_task"
    tasks = auth_client.get("/api/v1/tasks?limit=10").json()
    linked = next((t for t in tasks["items"] if t.get("related_contact_id")), None)
    assert linked is not None, tasks


def test_generate_marketing_copy_linkedin_pt(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={
        "message": "escreva um post para linkedin sobre vendas B2B",
    }).json()
    assert r["intent"] == "generate_marketing_copy", r
    assert "linkedin" in r["reply"].lower() or "vendas" in r["reply"].lower()


def test_generate_marketing_copy_en(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={
        "message": "write a post on linkedin about product-led growth",
    }).json()
    assert r["intent"] == "generate_marketing_copy", r
    assert "product-led growth" in r["reply"] or "linkedin" in r["reply"].lower()


def test_bare_pipeline_now_hits_summarize(auth_client):
    """Bug found in live probe: 'pipeline' alone should summarize."""
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "pipeline"}).json()
    assert r["intent"] == "summarize_pipeline", r


def test_plan_shows_help_for_unrecognized_step(auth_client):
    """When a step can't be classified, planner shows a hint instead of blank."""
    r = auth_client.post("/api/v1/jarvis/chat", json={
        "message": "zorlkbargle unknown thing and then pipeline",
    }).json()
    assert r["intent"] == "agent_plan"
    # Message is EN → hint appears in EN; also acceptable in PT if lang detection differs
    reply = r["reply"].lower()
    assert ("couldn't parse" in reply or "não entendi" in reply
            or "reformule" in reply or "reword" in reply)


def test_device_status_endpoint(auth_client):
    r = auth_client.get("/api/v1/jarvis/device-status").json()
    assert "tools" in r
    names = {t["name"] for t in r["tools"]}
    # Local-only tools now
    assert {"read_calendar", "auto_import_contacts", "list_files"} <= names


def test_agent_plan_multi_step_pt(auth_client):
    """Compound request splits into steps: 'pipeline e depois tarefas atrasadas'."""
    r = auth_client.post("/api/v1/jarvis/chat", json={
        "message": "resumo do pipeline e depois tarefas atrasadas",
    }).json()
    assert r["intent"] == "agent_plan", r
    # Both step outputs should appear
    assert "Passo 1" in r["reply"]
    assert "Passo 2" in r["reply"]


def test_agent_plan_and_then_en(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={
        "message": "summarize pipeline and then overdue tasks",
    }).json()
    assert r["intent"] == "agent_plan"
    assert "Passo 1" in r["reply"] or "Step 1" in r["reply"]


def test_agent_single_step_untouched(auth_client):
    """A single-step message must NOT go through the planner."""
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "pipeline"}).json()
    assert r["intent"] != "agent_plan", r


def test_search_everywhere_http_endpoint(auth_client):
    """New HTTP route that powers cmd-K in the frontend."""
    auth_client.post("/api/v1/contacts", json={"first_name": "Zenith", "last_name": "Zorro"})
    r = auth_client.get("/api/v1/jarvis/search-everywhere?q=zenith&limit=3").json()
    assert r["total"] >= 1
    names = [c["first_name"] for c in r["contacts"]]
    assert "Zenith" in names


def test_schedule_meeting_ambiguous_contact_asks_which(auth_client):
    """When 'schedule meeting with Ada' matches 2 contacts, Jarvis must ask which."""
    auth_client.post("/api/v1/contacts", json={"first_name": "Ada", "last_name": "Lovelace"})
    auth_client.post("/api/v1/contacts", json={"first_name": "Ada", "last_name": "Byron"})
    r = auth_client.post(
        "/api/v1/jarvis/chat",
        json={"message": "agende reunião com Ada amanhã às 15h"},
    ).json()
    assert r["intent"] == "schedule_meeting", r
    reply_low = r["reply"].lower()
    assert "encontrei" in reply_low or "found" in reply_low
    assert "ada" in reply_low
    tool_calls = r.get("tool_calls") or []
    ambig = [t for t in tool_calls if t.get("kind") == "contact_choice"]
    assert ambig, f"expected contact_choice tool_call, got {tool_calls}"
    assert len(ambig[0].get("options") or []) >= 2


def test_schedule_meeting_resolves_single_match(auth_client):
    """Single contact matching 'Grace' — meeting is created and linked."""
    auth_client.post("/api/v1/contacts", json={"first_name": "Grace", "last_name": "Hopper"})
    r = auth_client.post(
        "/api/v1/jarvis/chat",
        json={"message": "schedule a meeting with Grace tomorrow at 3pm"},
    ).json()
    assert r["intent"] == "schedule_meeting", r
    reply_low = r["reply"].lower()
    assert "meeting created" in reply_low or "reunião criada" in reply_low
    assert "grace" in reply_low
    # Confirm link marker "linked to" / "vinculado a"
    assert "linked to" in reply_low or "vinculado a" in reply_low


def test_ambiguity_resumption_by_number(auth_client):
    """User answers "1" after Jarvis asks which Ada — resumes with that contact."""
    auth_client.post("/api/v1/contacts", json={"first_name": "Ada", "last_name": "Lovelace"})
    auth_client.post("/api/v1/contacts", json={"first_name": "Ada", "last_name": "Byron"})
    r1 = auth_client.post(
        "/api/v1/jarvis/chat",
        json={"message": "agende reunião com Ada amanhã às 15h"},
    ).json()
    conv_id = r1["conversation_id"]
    assert r1["intent"] == "schedule_meeting", r1
    # Now pick option 1
    r2 = auth_client.post(
        "/api/v1/jarvis/chat",
        json={"message": "1", "conversation_id": conv_id},
    ).json()
    assert r2["intent"] == "schedule_meeting", r2
    reply2 = r2["reply"].lower()
    assert "reunião criada" in reply2 or "meeting created" in reply2
    assert "vinculado a" in reply2 or "linked to" in reply2


def test_reference_by_ordinal_after_top_opportunities(auth_client):
    """After 'top 3 opportunities', 'a segunda' returns details of the 2nd."""
    auth_client.post("/api/v1/opportunities", json={"name": "Alpha Deal", "amount": 100000, "probability": 90})
    auth_client.post("/api/v1/opportunities", json={"name": "Beta Deal", "amount": 50000, "probability": 80})
    auth_client.post("/api/v1/opportunities", json={"name": "Gamma Deal", "amount": 10000, "probability": 70})
    r1 = auth_client.post("/api/v1/jarvis/chat", json={"message": "top 3 opportunities"}).json()
    conv_id = r1["conversation_id"]
    assert r1["intent"] == "top_opportunities", r1
    # #1 = Alpha (100k*0.9=90k), #2 = Beta (50k*0.8=40k), #3 = Gamma
    r2 = auth_client.post("/api/v1/jarvis/chat", json={"message": "a segunda", "conversation_id": conv_id}).json()
    assert r2["intent"] == "opportunity_details", r2
    assert "Beta Deal" in r2["reply"]


def test_create_contact_from_chat(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "novo contato: Alice Silva"}).json()
    assert r["intent"] == "create_contact", r
    assert "Alice Silva" in r["reply"]
    # Verify it's actually in the DB
    list_r = auth_client.get("/api/v1/contacts").json()
    names = [f"{c['first_name']} {c.get('last_name','')}".strip() for c in list_r["items"]]
    assert "Alice Silva" in names


def test_create_company_from_chat(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "nova empresa: Acme Corp"}).json()
    assert r["intent"] == "create_company", r
    assert "Acme" in r["reply"]


def test_create_opportunity_from_chat_with_amount(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "nova oportunidade: Big Deal 50k"}).json()
    assert r["intent"] == "create_opportunity", r
    assert "Big Deal" in r["reply"]
    # 50k → 50000 → formatted "50,000" or similar
    assert "50" in r["reply"]


def test_current_date(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "que dia é hoje"}).json()
    assert r["intent"] == "current_date_time", r


def test_current_time(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "what time is it"}).json()
    assert r["intent"] == "current_date_time", r


def test_who_am_i_short(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "meu nome"}).json()
    assert r["intent"] == "who_am_i", r


def test_list_all_contacts(auth_client):
    auth_client.post("/api/v1/contacts", json={"first_name": "Alice", "last_name": "A"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "liste contatos"}).json()
    assert r["intent"] == "list_all_contacts", r
    assert "Alice" in r["reply"]


def test_list_all_companies(auth_client):
    auth_client.post("/api/v1/companies", json={"name": "Widget Co"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "todas empresas"}).json()
    assert r["intent"] == "list_all_companies", r
    assert "Widget" in r["reply"]


def test_list_all_opportunities(auth_client):
    auth_client.post("/api/v1/opportunities", json={"name": "Big Deal", "amount": 5000})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "mostre oportunidades"}).json()
    assert r["intent"] == "list_all_opportunities", r
    assert "Big Deal" in r["reply"]


def test_pipeline_total(auth_client):
    auth_client.post("/api/v1/opportunities", json={"name": "Deal A", "amount": 10000, "probability": 80})
    auth_client.post("/api/v1/opportunities", json={"name": "Deal B", "amount": 5000, "probability": 60})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "quanto vale meu pipeline"}).json()
    assert r["intent"] == "pipeline_total", r
    # 10000 raw sum + 5000 = 15000 (formatted)
    assert "15" in r["reply"]  # 15,000 or 15.000


def test_pipeline_show_natural_variants(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "me mostre o pipeline"}).json()
    assert r["intent"] == "summarize_pipeline", r


def test_pronoun_resolution_dela_delete(auth_client):
    """After creating 'Alice Silva', 'delete ela' resolves 'ela' → 'Alice Silva' and deletes."""
    r1 = auth_client.post("/api/v1/jarvis/chat", json={"message": "novo contato: Alice Silva"}).json()
    conv_id = r1["conversation_id"]
    r2 = auth_client.post("/api/v1/jarvis/chat",
                          json={"message": "delete ela", "conversation_id": conv_id}).json()
    assert r2["intent"] == "delete_contact", r2
    contacts = auth_client.get("/api/v1/contacts").json()
    assert contacts["total"] == 0


def test_pronoun_resolution_it_en(auth_client):
    """EN 'delete it' after creating opp resolves to that opp."""
    r1 = auth_client.post("/api/v1/jarvis/chat", json={"message": "new opportunity: Big Deal"}).json()
    conv_id = r1["conversation_id"]
    r2 = auth_client.post("/api/v1/jarvis/chat",
                          json={"message": "delete it", "conversation_id": conv_id}).json()
    assert r2["intent"] in ("delete_opportunity", "delete_bare"), r2


def test_multistep_reference_between_steps(auth_client):
    """Step 2 references contact created in step 1 → meeting linked automatically."""
    r = auth_client.post("/api/v1/jarvis/chat", json={
        "message": "crie contato Grace Hopper e agende reunião com Grace amanhã 15h",
    }).json()
    assert r["intent"] == "agent_plan", r
    contacts = auth_client.get("/api/v1/contacts").json()
    meetings = auth_client.get("/api/v1/meetings").json()
    assert contacts["total"] == 1
    assert meetings["total"] == 1
    # Meeting should link to the contact
    assert meetings["items"][0].get("related_contact_id") is not None


def test_schedule_meeting_implicit_when_no_preposition(auth_client):
    """'agende reunião com Ada amanhã 15h' works even without 'às/para' preposition."""
    auth_client.post("/api/v1/contacts", json={"first_name": "Ada", "last_name": "Byron"})
    r = auth_client.post("/api/v1/jarvis/chat", json={
        "message": "agende reunião com Ada amanhã 15h",
    }).json()
    assert r["intent"] == "schedule_meeting", r
    meetings = auth_client.get("/api/v1/meetings").json()
    assert meetings["total"] == 1


def test_planner_smart_split_e_between_verbs(auth_client):
    """'crie contato X e crie tarefa Y' → splits into 2 steps (smart-split)."""
    r = auth_client.post("/api/v1/jarvis/chat", json={
        "message": "crie contato Alice e crie tarefa: revisar contrato",
    }).json()
    assert r["intent"] == "agent_plan", r
    # Both entities should exist
    contacts = auth_client.get("/api/v1/contacts").json()
    tasks = auth_client.get("/api/v1/tasks").json()
    assert contacts["total"] == 1
    assert tasks["total"] == 1


def test_planner_no_split_when_e_not_before_verb(auth_client):
    """'novo contato: José e Maria' must NOT split — 'e' is part of a name."""
    r = auth_client.post("/api/v1/jarvis/chat", json={
        "message": "novo contato: José e Maria",
    }).json()
    # Should stay a single create_contact intent, not agent_plan
    assert r["intent"] == "create_contact", r


def test_onboarding_empty_state(auth_client):
    """'primeiros passos' on empty workspace → suggests seed demo."""
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "primeiros passos"}).json()
    assert r["intent"] == "onboarding", r
    # Empty state should mention seed
    assert "seed" in r["reply"].lower() or "demo" in r["reply"].lower()


def test_onboarding_after_seed(auth_client):
    """After seeding, onboarding switches to actionable next steps."""
    auth_client.post("/api/v1/jarvis/chat", json={"message": "popular demo"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "get started"}).json()
    assert r["intent"] == "onboarding", r
    # Should mention meetings/pipeline/dashboard actions
    reply_low = r["reply"].lower()
    assert any(kw in reply_low for kw in ("focus", "insights", "meeting", "pipeline", "dashboard"))


def test_onboarding_wizard_variants(auth_client):
    for msg in ("onboarding", "walkthrough", "como começar"):
        r = auth_client.post("/api/v1/jarvis/chat", json={"message": msg}).json()
        assert r["intent"] == "onboarding", (msg, r)


def test_seed_demo_populates_workspace(auth_client):
    """'popular demo' → seeds companies/contacts/leads/opps."""
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "popular demo"}).json()
    assert r["intent"] == "seed_demo", r
    contacts = auth_client.get("/api/v1/contacts").json()
    companies = auth_client.get("/api/v1/companies").json()
    assert contacts["total"] > 0
    assert companies["total"] > 0


def test_seed_demo_skips_when_not_empty(auth_client):
    """Second call to 'popular demo' respects skip-if-not-empty."""
    auth_client.post("/api/v1/jarvis/chat", json={"message": "popular demo"})
    r2 = auth_client.post("/api/v1/jarvis/chat", json={"message": "seed demo"}).json()
    assert r2["intent"] == "seed_demo", r2
    # Should say "already has data"
    assert "já tem" in r2["reply"] or "already" in r2["reply"]


def test_system_check_intent(auth_client):
    """system check → itemized diagnostic checklist."""
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "system check"}).json()
    assert r["intent"] == "system_check", r
    assert "System check" in r["reply"] or "Diagnóstico" in r["reply"]


def test_system_check_pt_variant(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "diagnóstico"}).json()
    assert r["intent"] == "system_check", r


def test_system_check_bare_status(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "status"}).json()
    assert r["intent"] == "system_check", r


def test_follow_up_com_x_creates_task(auth_client):
    """'follow-up com Alice amanhã 15h' → creates a task."""
    auth_client.post("/api/v1/contacts", json={"first_name": "Alice", "last_name": "Silva"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "follow-up com Alice amanhã 15h"}).json()
    # Reroutes to create_task under the hood
    assert r["intent"] == "create_task", r
    assert "Alice" in r["reply"]
    tasks = auth_client.get("/api/v1/tasks").json()
    assert tasks["total"] == 1


def test_ligar_x_amanha_creates_followup(auth_client):
    """'ligar Alice amanhã' → follow-up task."""
    auth_client.post("/api/v1/contacts", json={"first_name": "Alice", "last_name": "Silva"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "ligar Alice amanhã"}).json()
    assert r["intent"] == "create_task", r
    tasks = auth_client.get("/api/v1/tasks").json()
    assert tasks["total"] == 1
    assert "Follow-up" in tasks["items"][0]["title"] or "Alice" in tasks["items"][0]["title"]


def test_call_x_tomorrow_en(auth_client):
    auth_client.post("/api/v1/contacts", json={"first_name": "Alice", "last_name": "Silva"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "call Alice tomorrow"}).json()
    assert r["intent"] == "create_task", r


def test_ok_maps_to_thanks(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "ok"}).json()
    assert r["intent"] == "thanks", r


def test_blz_maps_to_thanks(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "blz"}).json()
    assert r["intent"] == "thanks", r


def test_meus_contatos_lists(auth_client):
    auth_client.post("/api/v1/contacts", json={"first_name": "Alice", "last_name": "A"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "meus contatos"}).json()
    assert r["intent"] == "list_all_contacts", r


def test_my_contacts_lists(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "my contacts"}).json()
    assert r["intent"] == "list_all_contacts", r


def test_meus_deals_lists(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "meus deals"}).json()
    assert r["intent"] == "list_all_opportunities", r


def test_mark_task_done_conclui_variant(auth_client):
    """'conclui a tarefa Follow up' → mark_task_done."""
    auth_client.post("/api/v1/tasks", json={"title": "Follow up"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "conclui a tarefa Follow up"}).json()
    assert r["intent"] == "mark_task_done", r


def test_mark_task_done_marque_como_feito(auth_client):
    auth_client.post("/api/v1/tasks", json={"title": "Review contract"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "marque como feito Review"}).json()
    assert r["intent"] == "mark_task_done", r


def test_delete_todos_leads_not_hijacked(auth_client):
    """'delete todos leads' must NOT be interpreted as bare-name delete."""
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "delete todos leads"}).json()
    # Should NOT match delete_bare (todos is a quantifier, not a name)
    assert r["intent"] != "delete_bare", r


def test_delete_bare_resumption_by_number(auth_client):
    """After 'delete Bob' shows 2 options, '1' actually deletes the first."""
    auth_client.post("/api/v1/contacts", json={"first_name": "Bob", "last_name": "A"})
    auth_client.post("/api/v1/companies", json={"name": "Bob Corp"})
    r1 = auth_client.post("/api/v1/jarvis/chat", json={"message": "delete Bob"}).json()
    assert r1["intent"] == "delete_bare", r1
    conv_id = r1["conversation_id"]
    r2 = auth_client.post("/api/v1/jarvis/chat",
                          json={"message": "1", "conversation_id": conv_id}).json()
    # Should execute the delete (not just show list again)
    assert r2["intent"] in ("delete_contact", "delete_company"), r2
    # One entity should now be deleted
    contacts = auth_client.get("/api/v1/contacts").json()
    companies = auth_client.get("/api/v1/companies").json()
    assert contacts["total"] + companies["total"] == 1


def test_delete_bare_name_unambiguous(auth_client):
    """'delete Alice' with only one Alice → deletes it."""
    auth_client.post("/api/v1/contacts", json={"first_name": "Alice", "last_name": "Silva"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "delete Alice"}).json()
    assert r["intent"] == "delete_contact", r
    # Verify actually deleted
    contacts = auth_client.get("/api/v1/contacts").json()
    assert contacts["total"] == 0


def test_delete_bare_name_ambiguous(auth_client):
    """'delete Bob' matches contact + company → returns disambiguation options."""
    auth_client.post("/api/v1/contacts", json={"first_name": "Bob", "last_name": "Contact"})
    auth_client.post("/api/v1/companies", json={"name": "Bob Corp"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "delete Bob"}).json()
    assert r["intent"] == "delete_bare", r
    assert "2" in r["reply"] or "dois" in r["reply"].lower()
    # Verify NOTHING was deleted
    contacts = auth_client.get("/api/v1/contacts").json()
    companies = auth_client.get("/api/v1/companies").json()
    assert contacts["total"] == 1
    assert companies["total"] == 1


def test_delete_bare_name_not_found(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "delete Ninguem"}).json()
    assert r["intent"] == "delete_bare", r
    assert "encontrado" in r["reply"].lower() or "nothing" in r["reply"].lower()


def test_quem_e_x_search(auth_client):
    """'quem é Alice' → global search."""
    auth_client.post("/api/v1/contacts", json={"first_name": "Alice", "last_name": "Silva"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "quem é Alice"}).json()
    assert r["intent"] == "search_everywhere", r
    assert "Alice" in r["reply"]


def test_who_is_x_search(auth_client):
    auth_client.post("/api/v1/contacts", json={"first_name": "Alice", "last_name": "Silva"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "who is Alice"}).json()
    assert r["intent"] == "search_everywhere", r


def test_tell_me_about_x(auth_client):
    auth_client.post("/api/v1/contacts", json={"first_name": "Alice", "last_name": "Silva"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "me fale de Alice"}).json()
    assert r["intent"] == "search_everywhere", r


def test_quantidade_count(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "quantidade de contatos"}).json()
    assert r["intent"] == "count_contacts", r


def test_search_bare_name_global(auth_client):
    """'busca Alice' (no entity kind) → global search across all entities."""
    auth_client.post("/api/v1/contacts", json={"first_name": "Alice", "last_name": "Silva"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "busca Alice"}).json()
    assert r["intent"] == "search_everywhere", r
    assert "Alice" in r["reply"]


def test_search_scoped_still_wins(auth_client):
    """'busca contato Alice' → find_contact, not search_everywhere."""
    auth_client.post("/api/v1/contacts", json={"first_name": "Alice", "last_name": "Silva"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "busca contato Alice"}).json()
    assert r["intent"] == "find_contact", r


def test_search_onde_esta(auth_client):
    """'onde está Alice' → global search."""
    auth_client.post("/api/v1/contacts", json={"first_name": "Alice", "last_name": "Silva"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "onde está Alice"}).json()
    assert r["intent"] == "search_everywhere", r


def test_urgent_tasks_pt(auth_client):
    auth_client.post("/api/v1/tasks", json={"title": "Urgent A", "priority": "urgent"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "tarefas urgentes"}).json()
    assert r["intent"] == "urgent_tasks", r
    assert "Urgent A" in r["reply"]


def test_urgent_tasks_en(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "urgent tasks"}).json()
    assert r["intent"] == "urgent_tasks", r


def test_meetings_this_week_en(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "meetings this week"}).json()
    assert r["intent"] == "upcoming_meetings", r


def test_meetings_today_en(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "meetings today"}).json()
    assert r["intent"] == "upcoming_meetings", r


def test_reunioes_esta_semana_no_accent(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "reunioes esta semana"}).json()
    assert r["intent"] == "upcoming_meetings", r


def test_opportunities_by_stage_pt(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "oportunidades por estagio"}).json()
    assert r["intent"] == "revenue_by_stage", r


def test_top_leads(auth_client):
    auth_client.post("/api/v1/leads", json={"first_name": "Ana", "last_name": "A", "score": 90})
    auth_client.post("/api/v1/leads", json={"first_name": "Bob", "last_name": "B", "score": 40})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "melhor lead"}).json()
    assert r["intent"] == "top_leads", r
    assert "Ana" in r["reply"]


def test_focus_short_variant(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "focar"}).json()
    assert r["intent"] == "help_me_focus", r


def test_focus_prioritize_variant(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "ajude me a priorizar"}).json()
    assert r["intent"] == "help_me_focus", r


def test_help_preciso_variant(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "preciso de ajuda"}).json()
    assert r["intent"] == "help", r


def test_who_are_you_sobre_variant(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "sobre o jarvis"}).json()
    assert r["intent"] == "who_are_you", r


def test_total_count_variants(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "total de contatos"}).json()
    assert r["intent"] == "count_contacts", r


def test_mark_won_shortcut(auth_client):
    """'ganhei Big Deal' should mark the opportunity as won."""
    auth_client.post("/api/v1/opportunities", json={"name": "Big Deal", "amount": 5000})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "ganhei Big Deal"}).json()
    assert r["intent"] == "mark_opportunity", r
    assert "won" in r["reply"].lower() or "ganha" in r["reply"].lower()


def test_mark_lost_shortcut_en(auth_client):
    auth_client.post("/api/v1/opportunities", json={"name": "Small Deal", "amount": 100})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "lost Small Deal"}).json()
    assert r["intent"] == "mark_opportunity", r


def test_bare_word_contatos_lists(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "contatos"}).json()
    assert r["intent"] == "list_all_contacts", r


def test_bare_word_empresas_lists(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "empresas"}).json()
    assert r["intent"] == "list_all_companies", r


def test_empty_note_body_rejected(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "nota: :"}).json()
    assert r["intent"] == "create_note", r
    notes = auth_client.get("/api/v1/notes").json()
    assert notes["total"] == 0


def test_create_task_empty_title_rejected(auth_client):
    """'crie tarefa:' (empty title) must NOT create a task with title = ':'."""
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "crie tarefa: "}).json()
    assert r["intent"] == "create_task", r
    assert "título" in r["reply"].lower() or "title" in r["reply"].lower()
    tasks = auth_client.get("/api/v1/tasks").json()
    assert tasks["total"] == 0, tasks


def test_create_contact_punctuation_only_name_rejected(auth_client):
    """'novo contato: :::::' (only punctuation) must NOT create a contact."""
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "novo contato: :::::"}).json()
    assert r["intent"] == "create_contact", r
    # Must have refused
    contacts = auth_client.get("/api/v1/contacts").json()
    assert contacts["total"] == 0, contacts


def test_create_contact_empty_name_rejected(auth_client):
    """'novo contato:' (empty after colon) must NOT create an empty contact."""
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "novo contato:"}).json()
    assert r["intent"] == "create_contact", r
    assert "nome" in r["reply"].lower() or "name" in r["reply"].lower()
    # Verify no contact was actually created
    contacts = auth_client.get("/api/v1/contacts").json()
    assert contacts["total"] == 0, contacts


def test_create_company_empty_name_rejected(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "nova empresa: "}).json()
    assert r["intent"] == "create_company", r
    assert "nome" in r["reply"].lower() or "name" in r["reply"].lower()
    companies = auth_client.get("/api/v1/companies").json()
    assert companies["total"] == 0


def test_create_opportunity_empty_name_rejected(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "nova oportunidade:"}).json()
    assert r["intent"] == "create_opportunity", r
    assert "nome" in r["reply"].lower() or "name" in r["reply"].lower()
    opps = auth_client.get("/api/v1/opportunities").json()
    assert opps["total"] == 0


def test_update_field_email_pt(auth_client):
    """'email do Alice é X' updates Alice's email."""
    auth_client.post("/api/v1/contacts", json={"first_name": "Alice", "last_name": "Silva", "email": "old@x.com"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "email do Alice é new@x.com"}).json()
    assert r["intent"] == "update_field", r
    contacts = auth_client.get("/api/v1/contacts").json()
    assert contacts["items"][0]["email"] == "new@x.com"


def test_update_field_amount_opportunity(auth_client):
    """'amount da oportunidade Big Deal = 50000' updates opp amount."""
    auth_client.post("/api/v1/opportunities", json={"name": "Big Deal", "amount": 1000})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "amount da oportunidade Big Deal = 50000"}).json()
    assert r["intent"] == "update_field", r
    opps = auth_client.get("/api/v1/opportunities").json()
    assert opps["items"][0]["amount"] == 50000.0


def test_update_field_en_reversed_order(auth_client):
    """'update Alice email = X' — EN order (verb subject field = value)."""
    auth_client.post("/api/v1/contacts", json={"first_name": "Alice", "last_name": "Silva", "email": "old@x.com"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "update Alice email = new@x.com"}).json()
    assert r["intent"] == "update_field", r


def test_update_field_missing_entity(auth_client):
    """'email do Ninguem é X' → polite not-found."""
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "email do Ninguem é x@y.com"}).json()
    assert r["intent"] == "update_field", r
    assert "não encontrei" in r["reply"].lower() or "nothing matches" in r["reply"].lower()


def test_undo_reverts_update_field(auth_client):
    """'desfaz' after 'email do Alice é X' reverts to the original email."""
    auth_client.post("/api/v1/contacts", json={"first_name": "Alice", "last_name": "Silva", "email": "orig@a.com"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "email do Alice é new@x.com"}).json()
    cid = r["conversation_id"]
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "desfaz", "conversation_id": cid}).json()
    assert r["intent"] == "undo_last", r
    contacts = auth_client.get("/api/v1/contacts").json()
    assert contacts["items"][0]["email"] == "orig@a.com"


def test_undo_of_undo_is_blocked(auth_client):
    """Two consecutive 'desfaz' after single update — the second finds nothing."""
    auth_client.post("/api/v1/contacts", json={"first_name": "Alice", "last_name": "Silva", "email": "orig@a.com"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "email do Alice é new@x.com"}).json()
    cid = r["conversation_id"]
    auth_client.post("/api/v1/jarvis/chat", json={"message": "desfaz", "conversation_id": cid})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "desfaz", "conversation_id": cid}).json()
    assert r["intent"] == "undo_last"
    assert "nada para desfazer" in r["reply"].lower() or "nothing to undo" in r["reply"].lower()


def test_clear_field_pt(auth_client):
    """'apaga o email do Alice' sets email to null."""
    auth_client.post("/api/v1/contacts", json={"first_name": "Alice", "last_name": "Silva", "email": "a@a.com"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "apaga o email do Alice"}).json()
    assert r["intent"] == "clear_field", r
    contacts = auth_client.get("/api/v1/contacts").json()
    assert contacts["items"][0]["email"] is None


def test_clear_field_en(auth_client):
    """'clear Alice phone' sets phone to null."""
    auth_client.post("/api/v1/contacts", json={"first_name": "Alice", "last_name": "Silva", "phone": "999"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "clear Alice phone"}).json()
    assert r["intent"] == "clear_field", r
    contacts = auth_client.get("/api/v1/contacts").json()
    assert contacts["items"][0]["phone"] is None


def test_clear_field_does_not_hijack_delete_bare(auth_client):
    """'delete Alice' (no field) still routes to delete_bare / delete_contact."""
    auth_client.post("/api/v1/contacts", json={"first_name": "Alice", "last_name": "Silva", "email": "a@a.com"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "delete Alice"}).json()
    assert r["intent"] in ("delete_contact", "delete_bare"), r


def test_daily_briefing(auth_client):
    """'briefing' returns morning-style summary; 'bom dia' still routes to greeting."""
    auth_client.post("/api/v1/jarvis/chat", json={"message": "seed dados de exemplo"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "briefing"}).json()
    assert r["intent"] == "daily_briefing", r
    assert "☀️" in r["reply"] or "briefing" in r["reply"].lower()
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "bom dia"}).json()
    assert r["intent"] == "greeting", r


def test_intent_gap_fixes_tick65(auth_client):
    """Tick 65 sweep: fixed 4 more phrasings."""
    cases = {
        "opps abertas": "open_opportunities",
        "reuniões da semana": "upcoming_meetings",
        "tasks hoje": "tasks_today",
        "e ai": "greeting",
    }
    for msg, expected in cases.items():
        r = auth_client.post("/api/v1/jarvis/chat", json={"message": msg}).json()
        assert r["intent"] == expected, (msg, r["intent"])


def test_me_lembra_when_first(auth_client):
    """'me lembra amanhã de ligar pra Alice' creates task with due_at set."""
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "me lembra amanhã de ligar pra Alice"}).json()
    assert r["intent"] == "create_task", r
    tasks = auth_client.get("/api/v1/tasks").json()
    assert tasks["total"] == 1
    assert tasks["items"][0]["due_at"] is not None


def test_me_lembra_with_time(auth_client):
    """'me lembre amanhã 15h de reunião' sets due_at with time."""
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "me lembre amanhã 15h de reunião"}).json()
    assert r["intent"] == "create_task", r
    tasks = auth_client.get("/api/v1/tasks").json()
    due = tasks["items"][0]["due_at"]
    assert due and "15:00" in due


def test_remember_fact_still_works(auth_client):
    """Regression: 'lembre: X' still routes to remember (not create_task)."""
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "lembre: buy milk"}).json()
    assert r["intent"] == "remember_fact", r


def test_suggest_respects_tone_concise(auth_client):
    """'estilo conciso' + sugestões = 'Top 3:' header only."""
    auth_client.post("/api/v1/jarvis/chat", json={"message": "estilo conciso"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "sugestões"}).json()
    assert r["intent"] == "suggest_next_action", r
    assert "Top 3" in r["reply"] and "prioridades" not in r["reply"].lower()


def test_pipeline_health_respects_tone_technical(auth_client):
    """'modo técnico' + pipeline health = 'pipeline.health:' header."""
    auth_client.post("/api/v1/jarvis/chat", json={"message": "seed dados de exemplo"})
    auth_client.post("/api/v1/jarvis/chat", json={"message": "modo técnico"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "pipeline health"}).json()
    assert r["intent"] == "pipeline_health", r
    assert "pipeline.health:" in r["reply"], r["reply"][:200]


def test_briefing_respects_tone_concise(auth_client):
    """'estilo conciso' + briefing = 1-line header (no 'liberdade')."""
    auth_client.post("/api/v1/jarvis/chat", json={"message": "estilo conciso"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "briefing"}).json()
    assert r["intent"] == "daily_briefing", r
    assert "liberdade" not in r["reply"].lower() and "liberty" not in r["reply"].lower()


def test_briefing_respects_tone_technical(auth_client):
    """'modo técnico' + briefing = 'Briefing[YYYY-MM-DD]' header."""
    auth_client.post("/api/v1/jarvis/chat", json={"message": "modo técnico"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "briefing"}).json()
    assert r["intent"] == "daily_briefing", r
    assert "Briefing[" in r["reply"], r["reply"][:200]


def test_create_task_nudge_when_no_deadline(auth_client):
    """Task without due date gets deadline nudge."""
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "crie tarefa Ligar pro Bob"}).json()
    assert r["intent"] == "create_task", r
    assert "prazo" in r["reply"].lower() or "deadline" in r["reply"].lower()


def test_create_opportunity_nudge_when_no_amount(auth_client):
    """Opp without amount gets a proactive nudge to set it."""
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "nova oportunidade: Big Deal"}).json()
    assert r["intent"] == "create_opportunity", r
    assert "amount" in r["reply"].lower() or "valor" in r["reply"].lower()


def test_create_contact_proactive_nudge_formal(auth_client):
    """JARVIS: after creating contact, formal tone offers next-action nudge."""
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "novo contato: Alice Silva"}).json()
    assert r["intent"] == "create_contact", r
    assert "adicione email" in r["reply"].lower() or "add email" in r["reply"].lower()


def test_create_contact_no_nudge_concise(auth_client):
    """Concise tone suppresses the proactive nudge."""
    auth_client.post("/api/v1/jarvis/chat", json={"message": "estilo conciso"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "novo contato: Bob Marley"}).json()
    assert r["intent"] == "create_contact"
    assert "💡" not in r["reply"]


def test_greeting_respects_tone_casual(auth_client):
    """After 'seja casual', greeting flips to casual voice ('opa', 'hey', 🙂)."""
    auth_client.post("/api/v1/jarvis/chat", json={"message": "seja casual"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "oi"}).json()
    assert r["intent"] == "greeting", r
    reply = r["reply"].lower()
    assert ("opa" in reply or "hey" in reply or "🙂" in r["reply"]), r["reply"]


def test_greeting_respects_tone_concise(auth_client):
    """After 'estilo conciso', greeting shrinks to 2 lines."""
    auth_client.post("/api/v1/jarvis/chat", json={"message": "estilo conciso"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "oi"}).json()
    assert r["intent"] == "greeting", r
    # Concise = 2 lines max
    assert r["reply"].count("\n") <= 2, r["reply"]


def test_set_tone_persists(auth_client):
    """Tick 81: 'seja formal' saves tone preference."""
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "seja formal"}).json()
    assert r["intent"] == "set_tone", r
    assert "formal" in r["reply"].lower() and ("ao dispor" in r["reply"].lower() or "at your service" in r["reply"].lower())


def test_set_tone_variants(auth_client):
    """Multiple tone phrasings."""
    for msg in ("modo casual", "be more technical", "estilo conciso", "seja mais amigável"):
        r = auth_client.post("/api/v1/jarvis/chat", json={"message": msg}).json()
        assert r["intent"] == "set_tone", (msg, r["intent"])


def test_pt_lang_detection_natural_queries(auth_client):
    """Tick 80: PT queries without accents should route to PT tone."""
    cases = {
        "quem é você": "planejo",  # who_are_you PT
        "como você está": "nominais",  # how_are_you PT
        "qual seu nome": "planejo",  # who_are_you PT
    }
    for msg, needle in cases.items():
        r = auth_client.post("/api/v1/jarvis/chat", json={"message": msg}).json()
        assert needle in r["reply"].lower(), (msg, r["reply"][:80])


def test_fallback_jarvis_tone(auth_client):
    """Unknown command → JARVIS-style suggestion, not the old 'quite get that'."""
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "xzczxczxcxz"}).json()
    reply = r["reply"].lower()
    assert "não reconheci" in reply or "not recognised" in reply, r


def test_seed_demo_jarvis_tone(auth_client):
    """Seed demo response uses new instrumented tone."""
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "seed dados de exemplo"}).json()
    reply = r["reply"].lower()
    assert "instanciado" in reply or "instanced" in reply, r


def test_workspaces_list_endpoint(auth_client):
    """Regression: GET /api/v1/workspaces returns current user's workspaces.
    Frontend calls this on bootstrap — 404 broke workspace selector silently."""
    r = auth_client.get("/api/v1/workspaces")
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body, list) and len(body) >= 1
    assert body[0].get("id") and body[0].get("name")


def test_jarvis_tone_pt(auth_client):
    """Tick 77+: JARVIS voice — crisp, ready, formal-witty."""
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "oi"}).json()
    assert r["intent"] == "greeting", r
    # Should include Jarvis brand + local emphasis + service offer
    reply = r["reply"].lower()
    assert "jarvis" in reply and "local" in reply and "briefing" in reply


def test_jarvis_tone_thanks(auth_client):
    """'obrigado' → 'Ao dispor.'"""
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "obrigado"}).json()
    assert r["intent"] == "thanks", r
    assert "ao dispor" in r["reply"].lower() or "at your service" in r["reply"].lower()


def test_jarvis_tone_goodbye(auth_client):
    """'tchau' → 'Em standby quando precisar.'"""
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "tchau"}).json()
    assert r["intent"] == "goodbye", r
    assert "standby" in r["reply"].lower()


def test_data_quality_flags_missing(auth_client):
    """'data quality' flags contacts w/o email, opps w/o amount."""
    auth_client.post("/api/v1/contacts", json={"first_name": "A"})  # no email
    auth_client.post("/api/v1/opportunities", json={"name": "Opp1"})  # no amount
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "data quality"}).json()
    assert r["intent"] == "data_quality", r
    assert "email" in r["reply"].lower() and "amount" in r["reply"].lower()


def test_data_quality_all_complete(auth_client):
    """Empty workspace → 'data complete'."""
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "qualidade dos dados"}).json()
    assert r["intent"] == "data_quality", r
    assert "completos" in r["reply"].lower() or "complete" in r["reply"].lower()


def test_convert_lead_creates_contact(auth_client):
    """'convert lead Grace' creates a contact + marks lead converted."""
    auth_client.post("/api/v1/leads", json={
        "first_name": "Grace", "last_name": "Hopper",
        "email": "grace@x.com", "phone": "999",
    })
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "convert lead Grace"}).json()
    assert r["intent"] == "convert_lead", r
    contacts = auth_client.get("/api/v1/contacts").json()
    assert contacts["total"] == 1
    assert contacts["items"][0]["email"] == "grace@x.com"


def test_convert_lead_twice_blocked(auth_client):
    """Second convert says 'already converted'."""
    auth_client.post("/api/v1/leads", json={"first_name": "Grace", "email": "g@x.com"})
    auth_client.post("/api/v1/jarvis/chat", json={"message": "convert lead Grace"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "convert lead Grace"}).json()
    assert r["intent"] == "convert_lead"
    assert "já foi convertido" in r["reply"].lower() or "already converted" in r["reply"].lower()


def test_convert_lead_not_found(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "convert lead Nonexistent"}).json()
    assert r["intent"] == "convert_lead"
    assert "não encontrado" in r["reply"].lower() or "not found" in r["reply"].lower()


def test_stats_by_owner(auth_client):
    """'pipeline by owner' groups open opps per user."""
    auth_client.post("/api/v1/jarvis/chat", json={"message": "seed dados de exemplo"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "pipeline by owner"}).json()
    assert r["intent"] == "stats_by_owner", r
    assert "👥" in r["reply"] or "owner" in r["reply"].lower() or "dono" in r["reply"].lower()


def test_pipeline_health(auth_client):
    """'pipeline health' returns diagnosis with counts + values + trends."""
    auth_client.post("/api/v1/jarvis/chat", json={"message": "seed dados de exemplo"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "pipeline health"}).json()
    assert r["intent"] == "pipeline_health", r
    assert "🩺" in r["reply"] or "Open" in r["reply"]


def test_pipeline_health_empty(auth_client):
    """Empty pipeline returns polite prompt to prospect."""
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "pipeline health"}).json()
    assert r["intent"] == "pipeline_health", r
    assert "prospect" in r["reply"].lower() or "prospectar" in r["reply"].lower() or "vazio" in r["reply"].lower() or "empty" in r["reply"].lower()


def test_hot_leads_default_threshold(auth_client):
    """'hot leads' returns leads with score >= 70 (default)."""
    auth_client.post("/api/v1/leads", json={"first_name": "A", "email": "a@a.com", "score": 90})
    auth_client.post("/api/v1/leads", json={"first_name": "B", "email": "b@b.com", "score": 40})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "hot leads"}).json()
    assert r["intent"] == "hot_leads", r
    assert "A" in r["reply"] and "B —" not in r["reply"]


def test_hot_leads_custom_threshold(auth_client):
    """'hot leads 50' lowers the threshold."""
    auth_client.post("/api/v1/leads", json={"first_name": "A", "email": "a@a.com", "score": 55})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "hot leads 50"}).json()
    assert r["intent"] == "hot_leads", r
    assert "A" in r["reply"]


def test_momentum_check(auth_client):
    """'momentum' returns MoM comparison of wins/revenue."""
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "momentum"}).json()
    assert r["intent"] == "momentum_check", r
    assert "Momentum" in r["reply"] or "momentum" in r["reply"].lower()


def test_momentum_variants(auth_client):
    """Alternate phrasings for momentum_check."""
    for msg in ("tendência", "evolução", "trend", "how are we doing this month"):
        r = auth_client.post("/api/v1/jarvis/chat", json={"message": msg}).json()
        assert r["intent"] == "momentum_check", (msg, r["intent"])


def test_bare_entity_details(auth_client):
    """Tick 69: 'oportunidade Big Deal' (no verb) → entity_details lookup."""
    auth_client.post("/api/v1/opportunities", json={"name": "Big Deal", "amount": 5000})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "oportunidade Big Deal"}).json()
    assert r["intent"] == "opportunity_details", r


def test_open_opps_short_form(auth_client):
    """'open opps' short EN form routes to open_opportunities."""
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "open opps"}).json()
    assert r["intent"] == "open_opportunities", r


def test_stale_opportunities_lists(auth_client):
    """'stale deals' returns list of open opps; doesn't hijack 'close stale'."""
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "stale deals"}).json()
    assert r["intent"] == "stale_opportunities", r
    # 'close stale opps' should still route to close_stale_opportunities (action)
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "close stale opportunities"}).json()
    assert r["intent"] == "close_stale_opportunities", r


def test_stale_opportunities_custom_threshold(auth_client):
    """'oportunidades paradas há 60 dias' uses 60-day threshold."""
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "oportunidades paradas há 60 dias"}).json()
    assert r["intent"] == "stale_opportunities", r
    assert "60d" in r["reply"] or "60 d" in r["reply"]


def test_analyze_lead_pt(auth_client):
    """'analisa lead Grace' returns a lead report."""
    auth_client.post("/api/v1/leads", json={
        "first_name": "Grace", "last_name": "Hopper", "email": "g@x.com",
        "source": "web", "score": 85,
    })
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "analisa lead Grace"}).json()
    assert r["intent"] == "analyze_lead", r
    assert "Grace" in r["reply"] and "g@x.com" in r["reply"]


def test_analyze_lead_not_found(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "analisa lead Nonexistent"}).json()
    assert r["intent"] == "analyze_lead", r
    assert "não encontrado" in r["reply"].lower() or "not found" in r["reply"].lower()


def test_analyze_company_pt(auth_client):
    """'analisa empresa Acme' returns full company report with contacts + pipeline."""
    resp = auth_client.post("/api/v1/companies", json={
        "name": "Acme Corp", "domain": "acme.com", "industry": "Software",
    })
    cid = resp.json()["id"]
    auth_client.post("/api/v1/contacts", json={
        "first_name": "Alice", "last_name": "Silva", "email": "a@acme.com", "company_id": cid,
    })
    auth_client.post("/api/v1/opportunities", json={
        "name": "Big", "amount": 100000, "company_id": cid,
    })
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "analisa empresa Acme"}).json()
    assert r["intent"] == "analyze_company", r
    assert "Acme" in r["reply"]
    assert "1" in r["reply"]  # contact count


def test_analyze_company_not_found(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "analisa empresa Ninguem"}).json()
    assert r["intent"] == "analyze_company", r
    assert "não encontrada" in r["reply"].lower() or "not found" in r["reply"].lower()


def test_analyze_contact_pt(auth_client):
    """'analisa contato Alice' returns full analysis with tip."""
    auth_client.post("/api/v1/contacts", json={
        "first_name": "Alice", "last_name": "Silva",
        "email": "alice@acme.com", "phone": "999", "job_title": "CTO",
    })
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "analisa contato Alice"}).json()
    assert r["intent"] == "analyze_contact", r
    assert "Alice" in r["reply"] and "alice@acme.com" in r["reply"]
    # No linked opportunities → nudge appears
    assert "oportunidade" in r["reply"].lower() or "opportunit" in r["reply"].lower()


def test_analyze_contact_not_found(auth_client):
    """'analisa contato Ninguem' returns polite not-found."""
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "analisa contato Ninguem"}).json()
    assert r["intent"] == "analyze_contact", r
    assert "não encontrado" in r["reply"].lower() or "not found" in r["reply"].lower()


def test_analyze_opportunity_pt(auth_client):
    """'analisa Big Deal' returns a report with amount + probability + tip."""
    auth_client.post("/api/v1/opportunities", json={"name": "Big Deal", "amount": 50000, "probability": 75})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "analisa Big Deal"}).json()
    assert r["intent"] == "analyze_opportunity", r
    assert "Big Deal" in r["reply"]
    assert "50" in r["reply"] or "50.000" in r["reply"]
    # High-prob tip should appear
    assert "fechar" in r["reply"].lower() or "closing" in r["reply"].lower()


def test_analyze_opportunity_en_variants(auth_client):
    """English variants: 'analyze Big Deal', 'how is Big Deal doing'."""
    auth_client.post("/api/v1/opportunities", json={"name": "Big Deal", "amount": 50000})
    for msg in ("analyze Big Deal", "how is Big Deal doing"):
        r = auth_client.post("/api/v1/jarvis/chat", json={"message": msg}).json()
        assert r["intent"] == "analyze_opportunity", (msg, r)


def test_analyze_opportunity_not_found(auth_client):
    """'analisa Nonexistent' returns polite not-found."""
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "analisa Foo Bar Nonexistent"}).json()
    assert r["intent"] == "analyze_opportunity", r
    assert "não encontrei" in r["reply"].lower() or "no opportunity" in r["reply"].lower()


def test_opportunities_by_amount_above(auth_client):
    """Tick 61: 'oportunidades acima de 10k' filters open opps by amount."""
    auth_client.post("/api/v1/opportunities", json={"name": "Small", "amount": 5000})
    auth_client.post("/api/v1/opportunities", json={"name": "Big", "amount": 500000})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "oportunidades acima de 10k"}).json()
    assert r["intent"] == "opportunities_by_amount", r
    assert "Big" in r["reply"] and "Small" not in r["reply"]


def test_opportunities_by_amount_below(auth_client):
    """'opportunities below 10k' returns only Small."""
    auth_client.post("/api/v1/opportunities", json={"name": "Small", "amount": 5000})
    auth_client.post("/api/v1/opportunities", json={"name": "Big", "amount": 500000})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "opportunities below 10000"}).json()
    assert r["intent"] == "opportunities_by_amount", r
    assert "Small" in r["reply"] and "Big" not in r["reply"]


def test_opportunities_by_amount_operator(auth_client):
    """'opportunities > 100000' operator form."""
    auth_client.post("/api/v1/opportunities", json={"name": "Big", "amount": 500000})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "opportunities > 100000"}).json()
    assert r["intent"] == "opportunities_by_amount", r


def test_schedule_meeting_weekday_and_marca(auth_client):
    """Tick 61: 'marca reuniao com Alice sexta' + 'na próxima segunda' variants."""
    auth_client.post("/api/v1/contacts", json={"first_name": "Alice", "email": "a@a.com"})
    for msg in [
        "agende reuniao com Alice sexta",
        "marca reuniao com Alice na sexta",
        "agende call com Alice na proxima segunda",
        "schedule meeting with Alice friday",
    ]:
        r = auth_client.post("/api/v1/jarvis/chat", json={"message": msg}).json()
        assert r["intent"] == "schedule_meeting", (msg, r["intent"])


def test_intent_gap_fixes_tick60(auth_client):
    """Bug-hunt sweep: verify tick 60 regex fixes hit the right intents.

    Covers PT-BR chat abbrevs (flw/fmz/tmj/tá bom), loose creation verbs (cria/adiciona),
    English variants (avg deal size, conversion rate), meta questions (como funciona).
    """
    cases = {
        "flw": "goodbye",
        "fmz": "thanks",
        "tá bom": "thanks",
        "tmj": "thanks",
        "quanto tem no pipeline": "pipeline_total",
        "cria um contato Bob": "create_contact",
        "avg deal size": "average_deal_size",
        "conversion rate": "win_rate",
        "qual seu nome": "who_are_you",
        "como funciona?": "help",
        "pra que serve?": "help",
    }
    for msg, expected in cases.items():
        r = auth_client.post("/api/v1/jarvis/chat", json={"message": msg}).json()
        assert r["intent"] == expected, (msg, r["intent"], expected)


def test_explain_last_empty(auth_client):
    """'explique isso' with no prior action → 'nothing to explain'."""
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "explique isso"}).json()
    assert r["intent"] == "explain_last", r
    assert "nada" in r["reply"].lower() or "nothing" in r["reply"].lower()


def test_explain_last_after_update_field(auth_client):
    """After a field update, 'explique isso' describes what happened."""
    auth_client.post("/api/v1/contacts", json={"first_name": "Alice", "email": "orig@a.com"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "email do Alice é new@x.com"}).json()
    cid = r["conversation_id"]
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "explique isso", "conversation_id": cid}).json()
    assert r["intent"] == "explain_last", r
    assert "email" in r["reply"] and "orig@a.com" in r["reply"] and "new@x.com" in r["reply"]


def test_explain_repeats_across_multiple_calls(auth_client):
    """Regression: 'explique isso' twice in a row both see the earlier mutation.

    Previous bug: routes_jarvis broke on the first assistant regardless of
    whether it had tool_calls — so the 2nd explain (whose prior was explain
    itself) saw no tool_calls. get_history also returned OLDEST messages.
    """
    auth_client.post("/api/v1/contacts", json={"first_name": "Alice", "email": "orig@a.com"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "email do Alice é new@x.com"}).json()
    cid = r["conversation_id"]
    for _ in range(3):
        r = auth_client.post("/api/v1/jarvis/chat", json={"message": "explique isso", "conversation_id": cid}).json()
        assert r["intent"] == "explain_last"
        assert "email" in r["reply"], r["reply"]


def test_bulk_delete_tasks_done(auth_client):
    """'apaga todas tarefas concluídas' deletes only done tasks."""
    auth_client.post("/api/v1/tasks", json={"title": "T1"})
    auth_client.post("/api/v1/tasks", json={"title": "T2", "status": "done"})
    auth_client.post("/api/v1/tasks", json={"title": "T3", "status": "done"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "apaga todas tarefas concluídas"}).json()
    assert r["intent"] == "bulk_delete_tasks", r
    tasks = auth_client.get("/api/v1/tasks").json()
    assert tasks["total"] == 1
    assert tasks["items"][0]["title"] == "T1"


def test_bulk_delete_tasks_overdue_english(auth_client):
    """'delete all overdue tasks' deletes only overdue tasks (filter between all/tasks)."""
    from datetime import datetime, timedelta, timezone
    overdue = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    auth_client.post("/api/v1/tasks", json={"title": "Old", "due_at": overdue})
    auth_client.post("/api/v1/tasks", json={"title": "Fresh"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "delete all overdue tasks"}).json()
    assert r["intent"] == "bulk_delete_tasks", r
    tasks = auth_client.get("/api/v1/tasks").json()
    assert [t["title"] for t in tasks["items"]] == ["Fresh"]


def test_bulk_delete_does_not_hijack_single_delete(auth_client):
    """'delete Bob' still routes to delete_contact / delete_bare."""
    auth_client.post("/api/v1/contacts", json={"first_name": "Bob", "email": "b@b.com"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "delete Bob"}).json()
    assert r["intent"] in ("delete_contact", "delete_bare"), r


def test_suggest_next_action_empty(auth_client):
    """Fresh workspace: 'o que devo fazer?' → onboarding suggestion."""
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "o que devo fazer?"}).json()
    assert r["intent"] == "suggest_next_action", r
    assert "🎯" in r["reply"] or "próxima" in r["reply"].lower() or "next" in r["reply"].lower()


def test_suggest_next_action_after_seed(auth_client):
    """After seeding demo data, 'sugestões' returns concrete opportunity-anchored actions."""
    auth_client.post("/api/v1/jarvis/chat", json={"message": "seed dados de exemplo"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "sugestões"}).json()
    assert r["intent"] == "suggest_next_action", r
    # Should reference at least one seeded opportunity or task
    assert "→" in r["reply"], r["reply"]


def test_suggest_next_action_variants(auth_client):
    """All the alternate phrasings should route here."""
    for msg in ("próximos passos", "next steps", "what should I do", "sugira", "recomendações"):
        r = auth_client.post("/api/v1/jarvis/chat", json={"message": msg}).json()
        assert r["intent"] == "suggest_next_action", (msg, r["intent"])


def test_help_chat_abbrev_vc_faz(auth_client):
    """'o q vc faz' / 'oq vc faz' → help intent (chat abbreviation)."""
    for msg in ("o q vc faz", "oq vc faz"):
        r = auth_client.post("/api/v1/jarvis/chat", json={"message": msg}).json()
        assert r["intent"] == "help", (msg, r)


def test_entity_details_bare_hint(auth_client):
    """'detalhes do contato' with no name → polite hint asking which one."""
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "detalhes do contato"}).json()
    assert r["intent"] == "entity_details", r
    assert "qual" in r["reply"].lower() or "which" in r["reply"].lower()


def test_clear_field_already_empty(auth_client):
    """Clearing an already-empty field says so."""
    auth_client.post("/api/v1/contacts", json={"first_name": "Alice", "last_name": "Silva"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "apaga o email do Alice"}).json()
    assert r["intent"] == "clear_field"
    assert "vazio" in r["reply"].lower() or "empty" in r["reply"].lower()


def test_undo_english_amount(auth_client):
    """'amount da oportunidade X = 5000' then 'undo' reverts to original amount."""
    auth_client.post("/api/v1/opportunities", json={"name": "Big Deal", "amount": 1000})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "amount da oportunidade Big Deal = 5000"}).json()
    cid = r["conversation_id"]
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "undo", "conversation_id": cid}).json()
    assert r["intent"] == "undo_last"
    opps = auth_client.get("/api/v1/opportunities").json()
    assert opps["items"][0]["amount"] == 1000.0


def test_contact_details_by_name(auth_client):
    auth_client.post("/api/v1/contacts", json={"first_name": "Alice", "last_name": "Silva", "email": "alice@x.com"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "detalhes do contato Alice"}).json()
    assert r["intent"] == "contact_details", r
    assert "Alice" in r["reply"]


def test_company_details_by_name(auth_client):
    auth_client.post("/api/v1/companies", json={"name": "Acme", "domain": "acme.com"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "detalhes da empresa Acme"}).json()
    assert r["intent"] == "company_details", r
    assert "Acme" in r["reply"]


def test_opportunity_details_by_name(auth_client):
    auth_client.post("/api/v1/opportunities", json={"name": "Big Deal", "amount": 1000})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "detalhes da oportunidade Big"}).json()
    assert r["intent"] == "opportunity_details", r
    assert "Big Deal" in r["reply"]


def test_entity_details_missing_returns_polite(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "detalhes do contato Zorro"}).json()
    assert r["intent"] == "contact_details", r
    assert "encontrado" in r["reply"].lower() or "not found" in r["reply"].lower()


def test_note_on_contact(auth_client):
    auth_client.post("/api/v1/contacts", json={"first_name": "Alice", "last_name": "Silva"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "nota no contato Alice: cliente VIP"}).json()
    assert r["intent"] == "note_on_entity", r
    assert "Alice" in r["reply"]


def test_note_on_company(auth_client):
    auth_client.post("/api/v1/companies", json={"name": "Acme"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "nota na empresa Acme: pagamento em dia"}).json()
    assert r["intent"] == "note_on_entity", r


def test_note_on_missing_entity(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "nota no contato Ninguem: teste"}).json()
    assert r["intent"] == "note_on_entity", r
    # Should say "não encontrei" politely
    assert "encontrei" in r["reply"].lower() or "no contact" in r["reply"].lower()


def test_average_deal_size(auth_client):
    auth_client.post("/api/v1/opportunities", json={"name": "A", "amount": 100000})
    auth_client.post("/api/v1/opportunities", json={"name": "B", "amount": 50000})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "ticket medio"}).json()
    assert r["intent"] == "average_deal_size", r
    # (100000 + 50000) / 2 = 75000 → formatted "75,000" or "75.000"
    assert "75" in r["reply"]


def test_go_home_dashboard(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "dashboard"}).json()
    assert r["intent"] == "go_home", r


def test_go_home_painel(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "painel"}).json()
    assert r["intent"] == "go_home", r


def test_count_deals_variant(auth_client):
    auth_client.post("/api/v1/opportunities", json={"name": "X", "amount": 100})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "quantos deals"}).json()
    assert r["intent"] == "count_opportunities", r


def test_opportunities_at_company_pt(auth_client):
    co = auth_client.post("/api/v1/companies", json={"name": "Widget Co"}).json()
    auth_client.post("/api/v1/opportunities", json={"name": "Widget Deal", "amount": 15000, "company_id": co["id"]})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "oportunidades da Widget"}).json()
    assert r["intent"] == "opportunities_at_company", r
    assert "Widget Deal" in r["reply"]


def test_closing_this_week(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "oportunidades desta semana"}).json()
    assert r["intent"] == "closing_this_week", r


def test_insights_bare(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "insights"}).json()
    assert r["intent"] == "insights", r


def test_insights_pt_variants(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "dicas"}).json()
    assert r["intent"] == "insights", r


def test_win_rate_intent(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "win rate"}).json()
    assert r["intent"] == "win_rate", r


def test_win_rate_pt_variant(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "conversao do funil"}).json()
    assert r["intent"] == "win_rate", r


def test_amount_this_month(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "quanto ganhei este mes"}).json()
    assert r["intent"] == "amount_this_period", r


def test_amount_lost_this_week(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "perdi quanto esta semana"}).json()
    assert r["intent"] == "amount_this_period", r


def test_tasks_today(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "tarefas de hoje"}).json()
    assert r["intent"] == "tasks_today", r


def test_my_tasks(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "minhas tarefas"}).json()
    assert r["intent"] == "tasks_today", r


def test_quem_trabalha_em_variant(auth_client):
    auth_client.post("/api/v1/companies", json={"name": "Acme Corp"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "quem trabalha em Acme"}).json()
    assert r["intent"] == "list_contacts_by_company", r


def test_opportunities_won_pt(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "oportunidades ganhas"}).json()
    assert r["intent"] == "opportunities_by_status", r


def test_opportunities_lost_en(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "lost opportunities"}).json()
    assert r["intent"] == "opportunities_by_status", r


def test_reminder_pt(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "lembre-me de ligar Foo amanhã 15h"}).json()
    assert r["intent"] == "create_task", r


def test_reminder_short_pt(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "lembrete: revisar contratos"}).json()
    assert r["intent"] == "create_task", r


def test_reminder_en(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "remind me to email Foo tomorrow"}).json()
    assert r["intent"] == "create_task", r


def test_create_note_with_crie(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "crie nota: acompanhar cliente amanhã"}).json()
    assert r["intent"] == "create_note", r


def test_busque_empresa_variant(auth_client):
    auth_client.post("/api/v1/companies", json={"name": "Widget Co"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "busque empresa Widget"}).json()
    assert r["intent"] == "find_company", r


def test_goodbye_sair_variant(auth_client):
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "sair"}).json()
    assert r["intent"] == "goodbye", r


def test_busque_contato_variant(auth_client):
    """Common pt-BR imperative 'busque' must resolve to find_contact."""
    auth_client.post("/api/v1/contacts", json={"first_name": "Mateus", "last_name": "Silva"})
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "busque contato Mateus"}).json()
    assert r["intent"] == "find_contact", r


def test_atividade_recente_natural_order(auth_client):
    """'atividade recente' (pt-BR natural order) must resolve to activity_timeline."""
    r = auth_client.post("/api/v1/jarvis/chat", json={"message": "atividade recente"}).json()
    assert r["intent"] == "activity_timeline", r


def test_reference_by_ordinal_after_contacts_at_company(auth_client):
    """After listing contacts at a company, 'a primeira' returns that contact's details."""
    # Create a company + two contacts at it
    co = auth_client.post("/api/v1/companies", json={"name": "Acme Corp"}).json()
    auth_client.post("/api/v1/contacts", json={"first_name": "Alice", "last_name": "Alpha", "company_id": co["id"], "email": "alice@acme.com"})
    auth_client.post("/api/v1/contacts", json={"first_name": "Bob", "last_name": "Beta", "company_id": co["id"], "email": "bob@acme.com"})
    r1 = auth_client.post("/api/v1/jarvis/chat", json={"message": "contatos da Acme"}).json()
    conv_id = r1["conversation_id"]
    assert r1["intent"] == "list_contacts_by_company", r1
    r2 = auth_client.post("/api/v1/jarvis/chat", json={"message": "a primeira", "conversation_id": conv_id}).json()
    assert r2["intent"] == "contact_details", r2
    # Alice or Bob should be in the reply (order by first_name asc → Alice first)
    assert "Alice" in r2["reply"] or "Bob" in r2["reply"]


def test_reference_by_hash_number_after_top_opportunities(auth_client):
    """After 'top 3 opportunities', '#1' returns the first."""
    auth_client.post("/api/v1/opportunities", json={"name": "Alpha Deal", "amount": 100000, "probability": 90})
    auth_client.post("/api/v1/opportunities", json={"name": "Beta Deal", "amount": 50000, "probability": 80})
    r1 = auth_client.post("/api/v1/jarvis/chat", json={"message": "top 2 opportunities"}).json()
    conv_id = r1["conversation_id"]
    r2 = auth_client.post("/api/v1/jarvis/chat", json={"message": "#1", "conversation_id": conv_id}).json()
    assert r2["intent"] == "opportunity_details", r2
    assert "Alpha Deal" in r2["reply"]


def test_ambiguity_resumption_by_word(auth_client):
    """'primeiro' / 'the first' resolves the same way."""
    auth_client.post("/api/v1/contacts", json={"first_name": "Ada", "last_name": "Lovelace"})
    auth_client.post("/api/v1/contacts", json={"first_name": "Ada", "last_name": "Byron"})
    r1 = auth_client.post(
        "/api/v1/jarvis/chat",
        json={"message": "agende reunião com Ada amanhã às 15h"},
    ).json()
    conv_id = r1["conversation_id"]
    r2 = auth_client.post(
        "/api/v1/jarvis/chat",
        json={"message": "primeiro", "conversation_id": conv_id},
    ).json()
    assert r2["intent"] == "schedule_meeting", r2
    reply2 = r2["reply"].lower()
    assert "reunião criada" in reply2 or "meeting created" in reply2
