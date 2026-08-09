"use client";

import { useState, type FormEvent } from "react";
import type { ContactContent } from "@aces/content";

export interface ContactFormProps {
  contact: ContactContent;
}

type Status = "idle" | "submitting" | "success" | "error";

export function ContactForm({ contact }: ContactFormProps) {
  const [status, setStatus] = useState<Status>("idle");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setStatus("submitting");

    const form = event.currentTarget;
    const data = Object.fromEntries(new FormData(form).entries());

    try {
      const response = await fetch("/api/contact", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      if (!response.ok) throw new Error("Request failed");
      setStatus("success");
      form.reset();
    } catch {
      setStatus("error");
    }
  }

  return (
    <div className="grid grid-cols-1 gap-12 lg:grid-cols-5">
      <div className="lg:col-span-2">
        <p className="text-sm leading-relaxed text-[var(--color-text-muted)]">
          {contact.body}
        </p>
        <dl className="mt-8 flex flex-col gap-4 text-sm">
          <div>
            <dt className="text-xs uppercase tracking-[0.2em] text-[var(--color-gold)]">
              Email
            </dt>
            <dd className="mt-1 text-[var(--color-text)]">{contact.emailPlaceholder}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-[0.2em] text-[var(--color-gold)]">
              Availability
            </dt>
            <dd className="mt-1 text-[var(--color-text)]">{contact.phonePlaceholder}</dd>
          </div>
        </dl>
      </div>

      <form
        onSubmit={handleSubmit}
        className="flex flex-col gap-5 lg:col-span-3"
      >
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
          <Field label="Name" name="name" type="text" required />
          <Field label="Email" name="email" type="email" required />
        </div>
        <Field label="Company" name="company" type="text" />
        <div className="flex flex-col gap-2">
          <label
            htmlFor="message"
            className="text-xs uppercase tracking-[0.2em] text-[var(--color-text-muted)]"
          >
            Message
          </label>
          <textarea
            id="message"
            name="message"
            required
            rows={5}
            className="border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-4 py-3 text-sm text-[var(--color-text)] outline-none transition-colors focus:border-[var(--color-gold)]"
          />
        </div>

        <div className="flex items-center gap-4 pt-2">
          <button
            type="submit"
            disabled={status === "submitting"}
            className="inline-flex items-center gap-2 border border-[var(--color-gold)] px-6 py-3.5 text-sm font-medium uppercase tracking-wide text-white bg-[linear-gradient(90deg,color-mix(in_srgb,var(--color-gold)_18%,transparent),color-mix(in_srgb,var(--color-accent)_12%,transparent))] transition-all duration-300 hover:bg-[linear-gradient(90deg,color-mix(in_srgb,var(--color-gold)_32%,transparent),color-mix(in_srgb,var(--color-accent)_20%,transparent))] disabled:opacity-60"
          >
            {status === "submitting" ? "Sending..." : "Send Message"}
          </button>
          {status === "success" ? (
            <span className="text-sm text-[var(--color-gold)]">
              Message received. We will follow up shortly.
            </span>
          ) : null}
          {status === "error" ? (
            <span className="text-sm text-[var(--color-accent-soft)]">
              Something went wrong. Please try again.
            </span>
          ) : null}
        </div>
      </form>
    </div>
  );
}

function Field({
  label,
  name,
  type,
  required,
}: {
  label: string;
  name: string;
  type: string;
  required?: boolean;
}) {
  return (
    <div className="flex flex-col gap-2">
      <label
        htmlFor={name}
        className="text-xs uppercase tracking-[0.2em] text-[var(--color-text-muted)]"
      >
        {label}
      </label>
      <input
        id={name}
        name={name}
        type={type}
        required={required}
        className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-4 py-3 text-sm text-[var(--color-text)] outline-none transition-colors focus:border-[var(--color-gold)]"
      />
    </div>
  );
}
