import { Cockpit } from "@/components/cockpit/Cockpit";

export default async function MissionPage(props: PageProps<"/missions/[id]">) {
  const { id } = await props.params;
  return <Cockpit missionId={id} />;
}
