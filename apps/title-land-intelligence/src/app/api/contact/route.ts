import { NextResponse } from "next/server";

interface ContactPayload {
  name?: string;
  email?: string;
  company?: string;
  message?: string;
}

export async function POST(request: Request) {
  const data = (await request.json()) as ContactPayload;

  if (!data.name || !data.email || !data.message) {
    return NextResponse.json(
      { ok: false, error: "Missing required fields." },
      { status: 400 }
    );
  }

  return NextResponse.json({ ok: true });
}
