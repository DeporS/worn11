
import { useTranslation } from "react-i18next";

const GroupsPage = () => {
  const { t } = useTranslation();
  return (
    <div>
      <h1>{t("groups.title")}</h1>
      <p>{t("groups.description")}</p>
    </div>
  );
};

export default GroupsPage;
