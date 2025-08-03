/** @odoo-module **/

import { CalendarModel } from "@web/views/calendar/calendar_model";
import { patch } from "@web/core/utils/patch";

patch(CalendarModel.prototype, {
    setup(params, services) {
        super.setup(params, services);
    },

    normalizeRecord(rawRecord) {
        let result = super.normalizeRecord(...arguments);
        if (this.env.searchModel.resModel == 'project.task') {
            result.as_custom_calendar = true;
            if (rawRecord.project_id) {
                result.project_id = rawRecord.project_id[1];
            }
        }
        return result;
    },
});
