# RTI request: TG RERA list of registered projects

Use this to ask the Telangana Real Estate Regulatory Authority for its complete list of registered projects as a spreadsheet. When it arrives, convert it to the JSON format (or ask for help in an issue) and import it; it fills in Hyderabad completely.

## How to send it

* **To:** The Public Information Officer, Telangana Real Estate Regulatory Authority, DTCP Building, Ground Floor, 640, A.C. Guards, Masab Tank (opp. PTI Building), Hyderabad – 500004. (Address as published on rera.telangana.gov.in; check the site's RTI section for the current PIO name.)
* **Fee:** ₹10 application fee for a state public authority in Telangana, usually paid by Indian Postal Order, demand draft or court-fee stamp payable to the PIO; check the accepted modes before sending. Citizens below the poverty line are exempt (attach proof).
* **Send by** speed post / registered post (keep the receipt) or in person, unless TG RERA lists an online RTI option on its website.
* **Timeline:** the PIO must reply within **30 days** (RTI Act, Section 7(1)). If there's no reply or you're refused, you can file a **first appeal** with the First Appellate Authority within 30 days of the deadline.
* Copying/CD charges, if any, are usually small; the PIO will tell you the amount.

## Letter (fill in the bracketed parts)

> **To**
> The Public Information Officer
> Telangana Real Estate Regulatory Authority
> DTCP Building, Ground Floor, 640, A.C. Guards, Masab Tank
> Hyderabad – 500004
>
> **Subject:** Request for information under Section 6(1) of the Right to Information Act, 2005 — list of projects registered with TG RERA
>
> Sir/Madam,
>
> I request the following information held by the Telangana Real Estate Regulatory Authority:
>
> 1. The complete list of real estate projects registered with TG RERA from 1 January 2017 to the date of this application, with the following details for each project, to the extent held by the Authority:
>    a. Project registration (certificate) number and date of registration;
>    b. Project name;
>    c. Promoter / company name;
>    d. District, mandal and village / locality, and project address;
>    e. Project type (residential apartments, villas, plotted development, commercial, mixed);
>    f. Proposed date of completion as declared at registration, and any extended completion date granted;
>    g. Current status (ongoing, completed, lapsed, revoked);
>    h. Total number of units / plots;
>    i. Name of the approving local authority (GHMC / HMDA / DTCP / other) and permit number, if recorded.
> 2. The list of projects whose registration has been revoked or has lapsed, with the date and order reference.
>
> Section 34(b) of the Real Estate (Regulation and Development) Act, 2016 requires the Authority to publish and maintain a website of records of registered projects for public viewing, so this information is already intended to be public.
>
> Under Section 7(9) of the RTI Act, I request the information **in electronic form**: an Excel (.xlsx) or CSV file sent by email to [your email], or on a CD/pen drive. If part of the information is not held in that form, please provide the rest in whatever form it is held, and tell me the cost of copies, if any.
>
> I have paid the application fee of ₹10 by [IPO / DD / court-fee stamp no. ______, dated ______].
>
> I am a citizen of India.
>
> Name: [your full name]
> Address: [postal address]
> Phone: [optional]
> Email: [for the electronic copy]
>
> Date: [date]                                                    Signature: [signature]

## After you receive the file

1. Save it as `data/tg_rera.xlsx` (or `.csv`).
2. Convert the columns to the JSON format in [DATA_FORMAT.md](DATA_FORMAT.md): `name`, `builder`, `city: "Hyderabad"`, `locality`, `rera_number`, `rera_status`, `rera_possession_date`, `status`. A spreadsheet export to CSV and a short script, or an issue on GitHub with the file attached, both work.
3. `python -m housingsearch import-json tg_rera.json` (or put it in `data/seed/rera_tg.json` so deployments include it).
