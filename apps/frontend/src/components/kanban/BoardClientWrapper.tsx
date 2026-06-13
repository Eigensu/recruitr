"use client";

import dynamic from "next/dynamic";

const KanbanBoard = dynamic(() => import("./Board"), { ssr: false });

interface Props {
  readonly positionId: string;
  readonly employees?: readonly { id: string; name: string }[];
  readonly clients?: readonly { id: string; label: string }[];
  readonly availableTags?: readonly string[];
}

export default function BoardClientWrapper(props: Props) {
  return <KanbanBoard {...props} />;
}
